"""A simulated milk centre: weather, milk deliveries, other loads, outages and the resulting meter history.

There is no public hourly meter data for a village milk centre, so the demo runs on this simulation. Every random
draw comes from one seeded generator, so the history is identical on every run.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from campus_energy_forecaster.outage import Backup

from .centre import DEFAULT_BACKUP, OPTIONAL_LOADS, Centre
from .thermal import Scenario, simulate

# Published load-shedding schedule for the centre's feeder: (weekday, start hour, end hour). Mon / Wed / Fri evenings.
SCHEDULE = [(0, 17, 21), (2, 17, 21), (4, 17, 21)]
MORNING, EVENING = (6, 30), (18, 0)       # nominal start of each collection; farmers arrive over ~45 minutes
PICKUP_HOUR = 9                            # the truck collects the tank every morning


@dataclass
class History:
    weather: pd.Series                     # hourly ambient temperature, C
    loads: pd.DataFrame                    # hourly demand of each non-cooler load, kW
    deliveries: list[tuple[pd.Timestamp, float]]
    sessions: pd.DataFrame                 # one row per collection: date, session, litres
    pickups: list[pd.Timestamp]
    outages: list[tuple[pd.Timestamp, pd.Timestamp]]
    frame: pd.DataFrame                    # 5-minute simulated state
    meter: pd.DataFrame                    # hourly grid meter per circuit (NaN during outages) + temp


def _weather(index: pd.DatetimeIndex, rng) -> pd.Series:
    days = index.normalize().unique()
    noise = np.zeros(len(days))
    for i in range(1, len(days)):
        noise[i] = 0.7 * noise[i - 1] + rng.normal(0, 1.2)
    season = 2.5 * np.sin(2 * np.pi * (days.day_of_year.values - 60) / 365.25)      # warming towards May/June
    daily_mean = pd.Series(30.0 + season + noise, index=days)
    mean = daily_mean.reindex(index.normalize()).to_numpy()
    swing = 6.0 * np.cos(2 * np.pi * (index.hour.values - 15) / 24)                 # hottest mid-afternoon
    return pd.Series(np.round(mean + swing + rng.normal(0, 0.4, len(index)), 2), index=index, name="temp")


def collection_times(day: pd.Timestamp, session: tuple[int, int], litres: float, chunks: int = 4):
    """Farmers arrive over ~45 minutes; split the session's milk into equal chunks 15 minutes apart."""
    t0 = day + pd.Timedelta(hours=session[0], minutes=session[1])
    return [(t0 + pd.Timedelta(minutes=15 * k), litres / chunks) for k in range(chunks)]


def _other_loads(index: pd.DatetimeIndex, temp: pd.Series, rng) -> pd.DataFrame:
    h = index.hour.values
    lights = np.where((h >= 18) & (h <= 22) | (h >= 5) & (h <= 6), 0.35, 0.03)
    office = np.where((h >= 7) & (h <= 20), 0.15 + 0.02 * np.clip(temp.to_numpy() - 28, 0, None), 0.02)
    heater = np.where((h == 6) | (h == 19), 1.5, 0.0)                               # hot water to wash cans
    pump = np.where(h == PICKUP_HOUR, 0.375, 0.0)                                   # 0.75 kW for half an hour
    df = pd.DataFrame({"lights": lights, "office": office, "water_heater": heater, "pump": pump}, index=index)
    jitter = rng.normal(1.0, 0.08, df.shape).clip(0.7, 1.3)
    return (df * jitter).round(3)[list(OPTIONAL_LOADS)]


def _outages(days: pd.DatetimeIndex, temp: pd.Series, rng) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Scheduled load-shedding happens on 85% of scheduled evenings and often overruns, more so on hot days.
    Unscheduled faults arrive at about one every 12 days."""
    out = []
    tmax = temp.groupby(temp.index.normalize()).max()
    for d in days:
        for wd, s, e in SCHEDULE:
            if d.day_of_week == wd and rng.random() < 0.85:
                start = d + pd.Timedelta(hours=s, minutes=int(rng.integers(0, 16)))
                overrun = max(-0.5, rng.normal(0.3, 0.5)) + 0.15 * max(0.0, tmax.loc[d] - 34)
                out.append((start, d + pd.Timedelta(hours=e) + pd.Timedelta(hours=overrun)))
        if rng.random() < 1 / 12:
            start = d + pd.Timedelta(minutes=int(rng.integers(0, 24 * 60)))
            out.append((start, start + pd.Timedelta(hours=0.25 + rng.exponential(1.5))))
    out.sort()
    merged = []
    for s, e in out:                                     # merge overlapping cuts
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return [(s.round("5min"), e.round("5min")) for s, e in merged]


def simulate_history(start="2026-03-02", days: int = 120, seed: int = 7, centre: Centre = Centre(),
                     backup: Backup = DEFAULT_BACKUP) -> History:
    """In the history the centre does what it does today: the battery carries every load until it is flat."""
    rng = np.random.default_rng(seed)
    t0 = pd.Timestamp(start)
    index = pd.date_range(t0, periods=24 * (days + 1), freq="h")         # one spare day for the last night
    temp = _weather(index, rng)
    loads = _other_loads(index, temp, rng)
    day_index = pd.date_range(t0, periods=days, freq="D")
    rows, deliveries = [], []
    for d in day_index:
        for name, sess, base in (("morning", MORNING, 480.0), ("evening", EVENING, 430.0)):
            litres = float(np.clip(rng.normal(base, 30) * (1 - 0.05 * (d.day_of_year - 60) / 120), 300, 495))
            rows.append({"date": d, "session": name, "litres": round(litres, 1)})
            deliveries += collection_times(d, sess, litres)
    pickups = [d + pd.Timedelta(hours=PICKUP_HOUR) for d in day_index[1:]]
    outages = _outages(day_index, temp, rng)
    scen = Scenario(deliveries=deliveries, pickups=pickups, outages=outages)
    frame = simulate(centre, backup, t0, 24 * days, temp, loads, scen)

    hourly = frame.resample("h").mean(numeric_only=True)
    on_grid = (frame["source"] == "grid").resample("h").mean()
    meter = pd.DataFrame({"temp": temp.loc[hourly.index]})
    load_on_grid = loads.loc[hourly.index]
    for c in OPTIONAL_LOADS:
        meter[c] = load_on_grid[c].where(on_grid == 1.0)
    meter["cooler"] = (frame["cooler_kw"].where(frame["source"] == "grid")).resample("h").mean().where(on_grid == 1.0)
    return History(temp, loads, deliveries, pd.DataFrame(rows), pickups, outages, frame, meter)
