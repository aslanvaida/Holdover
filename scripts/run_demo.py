"""Print tomorrow's Holdover alert for the simulated centre, and what would have happened under each strategy.

    python scripts/run_demo.py                 # Wednesday 3 June 2026
    python scripts/run_demo.py --day 2026-06-05
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from holdover.forecasting import fit_load_models  # noqa: E402
from holdover.pipeline import run_day  # noqa: E402
from holdover.simulate import simulate_history  # noqa: E402


def fmt(o):
    if o is None:
        return "n/a"
    state = "milk SAFE" if o.safe else f"milk UNSAFE from {o.unsafe_at:%H:%M}"
    return f"{state}, peak {o.max_tank_c:.1f}C, diesel {o.diesel_l:.1f} L"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="2026-06-03")
    args = ap.parse_args()
    day = pd.Timestamp(args.day)
    history = simulate_history()
    models = fit_load_models(history.meter, day - pd.Timedelta(hours=1))
    r = run_day(history, models, day)
    if r.alert is None:
        print(f"No cut expected on {day:%a %d %b}: no alert sent.")
        return
    print(r.alert)
    print("\n--- what actually happened (simulated) ---")
    for s, e in r.actual_cuts:
        print(f"cut {s:%H:%M}-{e:%H:%M}")
    print("as today:            ", fmt(r.truth_as_today))
    print("Holdover plan:       ", fmt(r.truth_plan))
    print("generator whole cut: ", fmt(r.truth_whole_generator))
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / f"alert_{day:%Y-%m-%d}.txt").write_text(r.alert + "\n")


if __name__ == "__main__":
    main()
