"""Turn a forecast day into a plan: will the milk stay safe through the cut, and what is the cheapest set of actions
that makes it safe?

Actions are tried in order of cost to the centre, each on top of the previous ones:
  1. switch off loads other than the cooler while on battery (free);
  2. chill the tank extra cold before the cut (a little grid electricity);
  3. run the generator, for the shortest window that keeps the milk safe (diesel).
An alternative that needs farmers' cooperation, bringing the evening milk in before the cut, is also checked.
"""
from dataclasses import dataclass, field, replace

import pandas as pd

from campus_energy_forecaster.outage import Backup

from .centre import LOAD_LABELS, Centre, Generator
from .simulate import EVENING, MORNING, PICKUP_HOUR, collection_times
from .thermal import Outcome, Scenario, simulate, summarise

H = pd.Timedelta(hours=1)
HORIZON_H = 33          # day 00:00 to the next morning's pickup


@dataclass
class Day:
    """Everything known (or forecast) at the start of ``day``."""
    day: pd.Timestamp
    ambient: pd.Series              # hourly forecast, C (covering day 00:00 + HORIZON_H)
    loads: pd.DataFrame             # hourly forecast kW of the non-cooler loads
    milk: dict[str, float]          # litres expected: {"morning": .., "evening": ..}
    outage: tuple[pd.Timestamp, pd.Timestamp]   # planned-for cut (start, end)
    tank_c: float
    tank_l: float
    battery_kwh: float | None = None
    evening_start: tuple[int, int] = EVENING

    def deliveries(self, evening_at: pd.Timestamp | None = None):
        d = self.day.normalize()
        ev = evening_at or d + pd.Timedelta(hours=self.evening_start[0], minutes=self.evening_start[1])
        nxt = d + pd.Timedelta(days=1)
        return (collection_times(d, MORNING, self.milk["morning"])
                + [(ev + pd.Timedelta(minutes=15 * k), self.milk["evening"] / 4) for k in range(4)]
                + collection_times(nxt, MORNING, self.milk["morning"]))

    def pickups(self):
        d = self.day.normalize()
        return [d + pd.Timedelta(hours=PICKUP_HOUR), d + pd.Timedelta(days=1, hours=PICKUP_HOUR)]


@dataclass
class Step:
    action: str
    outcome: Outcome
    detail: dict = field(default_factory=dict)


@dataclass
class Plan:
    day: Day
    as_today: Outcome
    steps: list[Step]
    final: Outcome
    generator_window: tuple[pd.Timestamp, pd.Timestamp] | None
    whole_cut_generator_l: float
    alternative: Step | None
    shed: list[str]
    scenario: Scenario

    @property
    def diesel_saved_l(self) -> float:
        return round(max(0.0, self.whole_cut_generator_l - self.final.diesel_l), 1) if self.generator_window else \
            round(self.whole_cut_generator_l, 1)


def run(day: Day, scen: Scenario, centre: Centre, backup: Backup, gen: Generator) -> Outcome:
    f = simulate(centre, backup, day.day, HORIZON_H, day.ambient, day.loads, scen, day.tank_c, day.tank_l,
                 day.battery_kwh)
    return summarise(f, day.outage[0], gen)


def _min_generator(day: Day, base: dict, centre, backup, gen, step_min: int):
    """Shortest generator window inside the cut that keeps the milk safe, or None if even the whole cut is not enough."""
    s, e = day.outage
    step = pd.Timedelta(minutes=step_min)
    n_steps = int((e - s) / step)
    for n in range(1, n_steps + 1):
        for k in range(0, n_steps - n + 1):
            w = (s + k * step, s + (k + n) * step)
            o = run(day, Scenario(**base, generator=[w]), centre, backup, gen)
            if o.safe:
                return w, o
    return None


def make_plan(day: Day, centre: Centre, backup: Backup, gen: Generator, step_min: int = 30,
              margin_c: float = 1.0) -> Plan:
    """Plans against a limit ``margin_c`` below ``centre.safe_max_c`` so forecast error has room."""
    s, e = day.outage
    plan_centre = replace(centre, safe_max_c=centre.safe_max_c - margin_c)
    common = dict(deliveries=day.deliveries(), pickups=day.pickups(), outages=[day.outage])
    as_today = run(day, Scenario(**common), plan_centre, backup, gen)
    in_cut = day.loads.loc[s:e - H].mean()
    shed = [n for n in day.loads.columns if in_cut.get(n, 0) > 0.05]
    pre = (max(day.day, s - 4 * H), s)
    ladders = [("shed", dict(keep_on_battery=())), ("prechill", dict(keep_on_battery=(), prechill=pre))]

    steps, prev_gen_h, scen, out = [], None, Scenario(**common), as_today
    first = _min_generator(day, common, plan_centre, backup, gen, step_min) if not as_today.safe else None
    prev_gen_h = None if first is None else (first[0][1] - first[0][0]) / H
    for name, kw in ladders:
        cand = Scenario(**common, **kw)
        o = run(day, cand, plan_centre, backup, gen)
        g = None if o.safe else _min_generator(day, {**common, **kw}, plan_centre, backup, gen, step_min)
        g_h = 0.0 if o.safe else (None if g is None else (g[0][1] - g[0][0]) / H)
        batt_gain = (o.battery_hours or 0) - (out.battery_hours or 0)
        helps = o.safe and not out.safe or (g_h is not None and (prev_gen_h is None or g_h < prev_gen_h))
        if name == "shed" and shed:
            helps = helps or batt_gain >= 0.1          # free, and buys time if the cut overruns
        if helps:
            steps.append(Step(name, o, {"loads": shed, "kw": round(float(in_cut[shed].sum()), 2),
                                         "battery_gain_h": round(batt_gain, 1), "generator_h": g_h,
                                         "from": pre[0], "to_c": centre.prechill_c}))
            scen, out, prev_gen_h, first = cand, o, g_h, g
    window = None
    if not out.safe and first is not None:
        window, out = first
        scen = replace(scen, generator=[window])
        steps.append(Step("generator", out, {"window": window}))

    whole = run(day, Scenario(**common, generator=[day.outage]), plan_centre, backup, gen)
    alternative = None
    ev = day.day.normalize() + pd.Timedelta(hours=day.evening_start[0], minutes=day.evening_start[1])
    if s <= ev + pd.Timedelta(minutes=45) and ev < e:          # evening collection falls in the cut
        early = (s - 2 * H).floor("30min")
        alt = run(day, replace(scen, generator=[], deliveries=day.deliveries(evening_at=early)), plan_centre, backup, gen)
        alternative = Step("early_milk", alt, {"evening_at": early})

    return Plan(day, as_today, steps, out, window, whole.diesel_l, alternative,
                [LOAD_LABELS.get(n, n) for n in shed], scen)
