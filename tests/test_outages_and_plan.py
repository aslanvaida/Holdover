import pandas as pd

from holdover.alert import compose
from holdover.centre import DEFAULT_BACKUP, Centre, Generator
from holdover.outages import predict_outage
from holdover.planner import Day, make_plan

SCHED = [(2, 17, 21)]                                  # Wednesdays 17-21


def test_scheduled_slot_uses_past_overruns():
    weds = pd.date_range("2026-04-01", periods=8, freq="7D")
    hist = [(d + pd.Timedelta(hours=17), d + pd.Timedelta(hours=21, minutes=30)) for d in weds]
    fc = predict_outage(weds[-1] + pd.Timedelta(days=7), hist, SCHED)
    assert fc.start.hour == 17 and fc.end_p90 == fc.start.normalize() + pd.Timedelta(hours=21, minutes=30)
    assert fc.probability == 1.0


def test_no_warning_on_unscheduled_quiet_day():
    assert predict_outage("2026-05-28", [], SCHED) is None


def test_plan_makes_evening_cut_safe_and_uses_less_diesel_than_whole_cut():
    day = pd.Timestamp("2026-06-03")
    idx = pd.date_range(day - pd.Timedelta(hours=1), periods=36, freq="h")
    loads = pd.DataFrame({"lights": 0.35, "office": 0.2, "water_heater": 0.0, "pump": 0.0}, index=idx)
    d = Day(day, pd.Series(34.0, index=idx), loads, {"morning": 480, "evening": 450},
            (day + pd.Timedelta(hours=17), day + pd.Timedelta(hours=22)), tank_c=4.0, tank_l=430)
    plan = make_plan(d, Centre(), DEFAULT_BACKUP, Generator())
    assert not plan.as_today.safe and plan.final.safe
    assert plan.generator_window is not None and plan.final.diesel_l < plan.whole_cut_generator_l
    fc = predict_outage(day, [(day - pd.Timedelta(days=7, hours=-17), day - pd.Timedelta(days=7, hours=-22))], SCHED)
    text = compose(plan, fc, Generator().litres_per_hour)
    assert "Run the generator" in text and "switch off" in text
