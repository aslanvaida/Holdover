"""One day end to end: forecast at midnight, plan, alert, then replay what actually happened under each strategy."""
from dataclasses import dataclass

import pandas as pd

from .centre import DEFAULT_BACKUP, OPTIONAL_LOADS, Centre, Generator
from .forecasting import forecast_loads, milk_forecast, weather_forecast
from .outages import OutageForecast, predict_outage
from .planner import HORIZON_H, Day, Plan, make_plan
from .simulate import EVENING, MORNING, SCHEDULE, History, collection_times
from .thermal import Outcome, Scenario, simulate, summarise
from .alert import compose

H = pd.Timedelta(hours=1)


@dataclass
class DayResult:
    day: pd.Timestamp
    forecast: OutageForecast | None
    plan: Plan | None
    alert: str | None
    actual_cuts: list
    truth_as_today: Outcome | None
    truth_plan: Outcome | None
    truth_whole_generator: Outcome | None


def _state_at(history: History, t):
    row = history.frame.loc[t]
    return float(row["tank_c"]), float(row["tank_l"]), float(row["battery_kwh"])


def forecast_day(history: History, models, day, centre=Centre(), backup=DEFAULT_BACKUP, gen=Generator()):
    day = pd.Timestamp(day)
    wx = weather_forecast(history.weather, day, HORIZON_H)
    tmax = float(wx.loc[day: day + pd.Timedelta(hours=23)].max())
    hist_tmax = history.weather.groupby(history.weather.index.normalize()).max()
    fc = predict_outage(day, history.outages, SCHEDULE, temp_max=tmax, history_temp_max=hist_tmax)
    if fc is None:
        return None, None, None
    loads = forecast_loads({k: v for k, v in models.items() if k in OPTIONAL_LOADS}, wx, day, HORIZON_H)
    load_df = pd.DataFrame({k: v["mid"] for k, v in loads.items()})[list(OPTIONAL_LOADS)]
    tank_c, tank_l, batt = _state_at(history, day)
    d = Day(day, wx.loc[day - H:], load_df, milk_forecast(history.sessions, day, stat="max"), (fc.start, fc.end_p90),
            tank_c, tank_l, batt)
    plan = make_plan(d, centre, backup, gen)
    return fc, plan, compose(plan, fc, gen.litres_per_hour)


def replay(history: History, day, plan: Plan | None, centre=Centre(), backup=DEFAULT_BACKUP, gen=Generator()):
    """Simulate the real day (actual weather, loads, milk and cuts) under: what the centre does today; Holdover's plan
    (plus its contingency: generator on if the cut outlasts the planned window); and generator for the whole cut."""
    day = pd.Timestamp(day)
    end = day + pd.Timedelta(hours=HORIZON_H)
    cuts = [(s, e) for s, e in history.outages if s < end and e > day]
    if not cuts:
        return cuts, None, None, None
    deliveries = [(t, v) for t, v in history.deliveries if day <= t < end]
    pickups = [t for t in history.pickups if day <= t < end]
    tank_c, tank_l, batt = _state_at(history, day)
    first = max(cuts[0][0], day)

    def go(**kw):
        f = simulate(centre, backup, day, HORIZON_H, history.weather, history.loads,
                     Scenario(deliveries=deliveries, pickups=pickups, outages=cuts, **kw), tank_c, tank_l, batt)
        return summarise(f, first, gen)

    as_today = go()
    whole = go(generator=cuts)
    if plan is None:
        return cuts, as_today, None, whole
    ps = plan.scenario
    planned_end = plan.day.outage[1]
    gen_windows = list(ps.generator) + [(planned_end, e) for s, e in cuts if e > planned_end and s < planned_end]
    followed = go(keep_on_battery=ps.keep_on_battery, prechill=ps.prechill, generator=gen_windows)
    return cuts, as_today, followed, whole


def run_day(history: History, models, day, **kw) -> DayResult:
    fc, plan, alert = forecast_day(history, models, day, **kw)
    cuts, a, p, w = replay(history, day, plan, **kw)
    return DayResult(pd.Timestamp(day), fc, plan, alert, cuts, a, p, w)
