"""Backtest Holdover on the last five weeks of the simulated centre.

For every day: forecast at midnight (weather forecast with error, milk from the last week, loads from the quantile
model, the cut from the schedule and past cuts), plan, then replay the real day under three strategies:
  as today        battery carries everything until it is flat, no generator;
  Holdover        the plan, plus "if power is not back by the planned end, run the generator until it is";
  generator       run the generator for the whole cut (the "just in case" habit).

Writes reports/backtest.json and reports/backtest.md.

    python scripts/backtest.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from holdover.centre import Generator  # noqa: E402
from holdover.forecasting import fit_load_models  # noqa: E402
from holdover.pipeline import run_day  # noqa: E402
from holdover.simulate import simulate_history  # noqa: E402

TEST_START, TEST_END = "2026-05-25", "2026-06-28"


def main():
    history = simulate_history()
    models = fit_load_models(history.meter, pd.Timestamp(TEST_START) - pd.Timedelta(hours=1))
    gen = Generator()
    rows = []
    for day in pd.date_range(TEST_START, TEST_END, freq="D"):
        r = run_day(history, models, day)
        real = [(s, e) for s, e in r.actual_cuts if s >= day]
        row = {"day": str(day.date()), "warned": r.forecast is not None, "cut": bool(real)}
        if r.forecast is not None:
            row.update(pred_start=str(r.forecast.start), pred_end_p90=str(r.forecast.end_p90),
                       pred_safe_as_today=r.plan.as_today.safe, pred_unsafe_at=str(r.plan.as_today.unsafe_at),
                       pred_battery_h=r.plan.as_today.battery_hours,
                       plan_generator=None if r.plan.generator_window is None else [str(t) for t in r.plan.generator_window])
        if real:
            row.update(cut_start=str(real[0][0]), cut_end=str(real[-1][1]))
        if r.truth_as_today is not None:
            row.update(safe_as_today=r.truth_as_today.safe, safe_whole_generator=r.truth_whole_generator.safe,
                       diesel_whole_generator=r.truth_whole_generator.diesel_l,
                       actual_unsafe_at=str(r.truth_as_today.unsafe_at),
                       actual_battery_h=r.truth_as_today.battery_hours)
        if r.truth_plan is not None:
            row.update(safe_holdover=r.truth_plan.safe, diesel_holdover=r.truth_plan.diesel_l)
        rows.append(row)

    df = pd.DataFrame(rows)
    cut = df[df["cut"]]
    warned_cut = cut[cut["warned"]]
    missed = cut[~cut["warned"]]
    false_alarm = df[df["warned"] & ~df["cut"]]
    # how long the battery lasts with nothing switched off: forecast at midnight vs the real day, on days the cut was
    # warned about and started at the scheduled time (so the start-time error does not dominate)
    ok = warned_cut.dropna(subset=["pred_battery_h", "actual_battery_h"])
    ok = ok[(pd.to_datetime(ok["cut_start"]) - pd.to_datetime(ok["pred_start"])).abs() <= pd.Timedelta(minutes=30)]
    err_min = (ok["pred_battery_h"] - ok["actual_battery_h"]) * 60
    summary = {
        "days": len(df), "days_with_cut": int(len(cut)), "warned_and_cut": int(len(warned_cut)),
        "missed_cuts": int(len(missed)), "false_alarms": int(len(false_alarm)),
        "milk_lost_days": {
            "as_today": int((~cut["safe_as_today"].astype(bool)).sum()),
            "holdover": int((~warned_cut["safe_holdover"].astype(bool)).sum() + (~missed["safe_as_today"].astype(bool)).sum()),
            "generator_whole_cut": int((~cut["safe_whole_generator"].astype(bool)).sum()),
        },
        "diesel_l_on_warned_days": {
            "holdover": round(float(warned_cut["diesel_holdover"].sum()), 1),
            "generator_whole_cut": round(float(warned_cut["diesel_whole_generator"].sum()), 1),
        },
        "battery_runtime_error_min": {"n": int(len(err_min)), "mean_abs": round(float(err_min.abs().mean()), 0),
                                      "max_abs": round(float(err_min.abs().max()), 0)},
    }
    d = summary["diesel_l_on_warned_days"]
    saved = d["generator_whole_cut"] - d["holdover"]
    summary["diesel_saved_l"] = round(saved, 1)
    summary["diesel_saved_usd"] = round(saved * gen.diesel_usd_per_l, 2)
    summary["co2_saved_kg"] = round(saved * gen.co2_kg_per_l, 1)

    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / "backtest.json").write_text(json.dumps({"summary": summary, "days": rows}, indent=2, default=str))
    m = summary["milk_lost_days"]
    md = f"""# Backtest: {TEST_START} to {TEST_END} (simulated centre)

All numbers come from the simulated centre in `holdover/simulate.py`, not from a real one. They show the method works
end to end and how its parts trade off, not what a real centre would save.

| | |
|---|---|
| Days | {summary['days']} |
| Days with a power cut | {summary['days_with_cut']} |
| Cuts warned about the night before | {summary['warned_and_cut']} |
| Cuts not warned about (unscheduled faults) | {summary['missed_cuts']} |
| Warnings with no cut (load-shedding skipped) | {summary['false_alarms']} |

**Days on which the milk went unsafe**

| Strategy | Days |
|---|---|
| As today (battery until flat, no generator) | {m['as_today']} |
| Holdover plan (and as today on days with no warning) | {m['holdover']} |
| Generator for the whole cut | {m['generator_whole_cut']} |

**Diesel on warned days:** Holdover {d['holdover']} L vs {d['generator_whole_cut']} L running the generator for the whole
cut, saving {summary['diesel_saved_l']} L (about ${summary['diesel_saved_usd']}, {summary['co2_saved_kg']} kg CO2) over
{summary['warned_and_cut']} cuts.

**Battery runtime, forecast the night before vs the real day** (nothing switched off, cuts that started on
schedule): mean absolute error {summary['battery_runtime_error_min']['mean_abs']:.0f} min, worst
{summary['battery_runtime_error_min']['max_abs']:.0f} min, over {summary['battery_runtime_error_min']['n']} cuts.

In this simulation the milk's "unsafe from" time is almost always set by the chilling rule (fresh evening milk must be
at or below 8 C within 3 hours of the last delivery), so it is 21:45 on most cut days; the battery runs out well before
the milk would warm up on its own. That is the main finding for the explainer: the risk is chilling the evening milk,
not keeping cold milk cold.
"""
    (out / "backtest.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
