"""Milk tank temperature and power source, simulated in 5-minute steps.

The model is a single well-mixed tank:
  * fresh milk mixes in at ``Centre.milk_in_c``;
  * heat leaks in at ``UA * (ambient - milk)``;
  * when the cooler has power it removes heat (up to ``cooling_kw_th``) to reach its setpoint, using
    ``heat / COP(ambient)`` of electricity;
  * power comes from the grid, else the generator (if it is scheduled to run), else the battery, else nothing.

Milk is *unsafe* at a step when it is above ``safe_max_c`` and more than ``chill_window_h`` has passed since the last
delivery (fresh milk is allowed that long to come down).
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from campus_energy_forecaster.outage import Backup

from .centre import MILK_CP_KJ_PER_KG_K, MILK_DENSITY_KG_PER_L, Centre, Generator

STEP = pd.Timedelta(minutes=5)
DT_H = STEP / pd.Timedelta(hours=1)
KJ_PER_K_PER_L = MILK_DENSITY_KG_PER_L * MILK_CP_KJ_PER_KG_K

Interval = tuple[pd.Timestamp, pd.Timestamp]
GRID, GEN, BATTERY, NONE = "grid", "generator", "battery", "none"


@dataclass
class Scenario:
    deliveries: list[tuple[pd.Timestamp, float]]       # (time, litres)
    pickups: list[pd.Timestamp] = field(default_factory=list)   # the truck empties the tank
    outages: list[Interval] = field(default_factory=list)
    generator: list[Interval] = field(default_factory=list)     # when the generator is switched on
    keep_on_battery: tuple[str, ...] | None = None     # other loads the battery serves besides the cooler; None = all
    prechill: Interval | None = None                   # run the tank at Centre.prechill_c during this interval


def _mask(index: pd.DatetimeIndex, intervals) -> np.ndarray:
    m = np.zeros(len(index), bool)
    for s, e in intervals:
        m |= (index >= s) & (index < e)
    return m


def _events(index: pd.DatetimeIndex, times, values=None) -> np.ndarray:
    out = np.zeros(len(index))
    for k, t in enumerate(times):
        i = index.searchsorted(t)
        if 0 <= i < len(index):
            out[i] += 1.0 if values is None else values[k]
    return out


def _per_step(hourly: pd.Series, index: pd.DatetimeIndex) -> np.ndarray:
    """Linear interpolation of an hourly series onto the step index."""
    s = hourly.reindex(hourly.index.union(index)).interpolate("time").reindex(index)
    return s.ffill().bfill().to_numpy(float)


def simulate(centre: Centre, backup: Backup, start, hours: float, ambient: pd.Series, loads: pd.DataFrame,
             scenario: Scenario, tank_c: float | None = None, tank_l: float = 0.0,
             battery_kwh: float | None = None) -> pd.DataFrame:
    """Step-by-step state from ``start`` for ``hours``; each row holds the state at the end of its 5-minute step. ``ambient`` is hourly air temperature (C) and ``loads`` hourly kW
    for each non-cooler load; both must cover the period. Returns one row per 5-minute step."""
    start = pd.Timestamp(start)
    idx = pd.date_range(start, periods=int(round(hours / DT_H)), freq=STEP)
    amb = _per_step(ambient, idx)
    names = list(loads.columns)
    load_arr = loads.reindex(idx.floor("h")).fillna(0.0).to_numpy(float)
    keep = np.ones(len(names), bool) if scenario.keep_on_battery is None else \
        np.array([n in scenario.keep_on_battery for n in names], bool)
    delivered = _events(idx, [t for t, _ in scenario.deliveries], [v for _, v in scenario.deliveries])
    pickup = _events(idx, scenario.pickups) > 0
    out = _mask(idx, scenario.outages)
    gen = _mask(idx, scenario.generator)
    pre = _mask(idx, [scenario.prechill]) if scenario.prechill else np.zeros(len(idx), bool)

    usable = backup.usable_kwh
    T = centre.setpoint_c if tank_c is None else float(tank_c)
    V = float(tank_l)
    batt = usable if battery_kwh is None else float(battery_kwh)
    since_delivery = 10**9                  # whole steps since the last delivery (integer: no float drift)
    window_steps = round(centre.chill_window_h / DT_H)
    cols = {k: np.empty(len(idx)) for k in ("tank_c", "tank_l", "battery_kwh", "cooler_kw", "other_kw", "grid_kw")}
    source = np.empty(len(idx), dtype=object)
    unsafe = np.zeros(len(idx), bool)

    for i in range(len(idx)):
        if pickup[i]:
            V = 0.0
        if delivered[i] > 0:
            T = centre.milk_in_c if V <= 0 else (T * V + centre.milk_in_c * delivered[i]) / (V + delivered[i])
            V += delivered[i]
            since_delivery = 0
        if not out[i]:
            src = GRID
        elif gen[i]:
            src = GEN
        elif batt > 1e-9:
            src = BATTERY
        else:
            src = NONE

        heat_cap = V * KJ_PER_K_PER_L                                     # kJ/K
        leak_kw = centre.ua_w_per_k * (amb[i] - T) / 1000.0 if V > 0 else 0.0
        q = 0.0
        if src != NONE and V > 0:
            sp = centre.prechill_c if pre[i] else centre.setpoint_c
            need = (T - sp) * heat_cap / (DT_H * 3600.0) + leak_kw
            q = min(max(need, 0.0), centre.cooling_kw_th)
        cooler_kw = q / centre.cop(amb[i])
        other_kw = 0.0 if src == NONE else float(load_arr[i][keep].sum() if src == BATTERY else load_arr[i].sum())

        if src == BATTERY:
            draw = (cooler_kw + other_kw) * DT_H
            if draw > batt:                       # battery runs out part-way through the step
                frac = batt / draw
                q, cooler_kw, other_kw, batt = q * frac, cooler_kw * frac, other_kw * frac, 0.0
            else:
                batt -= draw
        charge_kw = 0.0
        if src == GRID and batt < usable:
            charge_kw = min(centre.charger_kw, (usable - batt) / DT_H)
            batt += charge_kw * DT_H

        if V > 0:
            T += (leak_kw - q) * DT_H * 3600.0 / heat_cap
        since_delivery += 1
        unsafe[i] = V > 0 and T > centre.safe_max_c and since_delivery > window_steps

        cols["tank_c"][i], cols["tank_l"][i], cols["battery_kwh"][i] = T, V, batt
        cols["cooler_kw"][i], cols["other_kw"][i] = cooler_kw, other_kw
        cols["grid_kw"][i] = (cooler_kw + other_kw + charge_kw) if src == GRID else 0.0
        source[i] = src

    frame = pd.DataFrame(cols, index=idx)
    frame["source"], frame["unsafe"], frame["ambient_c"] = source, unsafe, amb
    return frame


@dataclass
class Outcome:
    safe: bool                       # milk never unsafe in the simulated period
    unsafe_at: pd.Timestamp | None   # first unsafe moment
    safe_hours: float | None         # hours from the outage start until milk is unsafe (None = safe throughout)
    battery_hours: float | None      # hours the battery carried the centre before running flat (None = never flat)
    holdover_hours: float | None     # hours after the battery ran flat until milk was unsafe
    diesel_l: float
    max_tank_c: float


def summarise(frame: pd.DataFrame, outage_start, generator: Generator) -> Outcome:
    outage_start = pd.Timestamp(outage_start)
    bad = frame.index[frame["unsafe"].to_numpy()]
    unsafe_at = bad[0] if len(bad) else None
    flat = frame.index[(frame["source"] == NONE).to_numpy() & (frame.index >= outage_start)]
    flat_at = flat[0] if len(flat) else None
    h = pd.Timedelta(hours=1)
    safe_hours = None if unsafe_at is None else max(0.0, (unsafe_at - outage_start) / h)
    battery_hours = None if flat_at is None else (flat_at - outage_start) / h
    holdover = None if (unsafe_at is None or flat_at is None) else max(0.0, (unsafe_at - flat_at) / h)
    diesel = float((frame["source"] == GEN).sum() * DT_H * generator.litres_per_hour)
    return Outcome(unsafe_at is None, unsafe_at, safe_hours, battery_hours, holdover, round(diesel, 2),
                   round(float(frame["tank_c"].where(frame["tank_l"] > 0).max()), 1))
