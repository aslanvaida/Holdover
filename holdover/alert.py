"""The SMS / WhatsApp text the centre manager receives."""
import pandas as pd

from .outages import OutageForecast
from .planner import Plan


def _t(ts: pd.Timestamp) -> str:
    return ts.strftime("%H:%M")


def _h(x: float | None) -> str:
    return "safe" if x is None else f"{x:.1f} h"


def compose(plan: Plan, forecast: OutageForecast, gen_litres_per_hour: float) -> str:
    d = plan.day
    s, e = d.outage
    hot = float(d.ambient.loc[s:e].max())
    ev = d.day.normalize() + pd.Timedelta(hours=d.evening_start[0], minutes=d.evening_start[1])
    lines = [f"Holdover alert, {d.day:%a %d %b}",
             f"Power cut likely {_t(forecast.start)}-{_t(forecast.end_p50)}, may run to {_t(forecast.end_p90)} "
             f"({forecast.probability:.0%} of recent {forecast.start:%A}s). Up to {hot:.0f}C.",
             f"Evening milk ~{d.milk['evening']:.0f} L at {_t(ev)}."]
    a = plan.as_today
    if a.safe:
        lines.append("Battery alone keeps the milk safe. No action needed.")
        return "\n".join(lines)
    batt = f"Battery lasts {a.battery_hours:.1f} h; " if a.battery_hours is not None else ""
    lines.append(f"{batt}milk unsafe from {_t(a.unsafe_at)} if nothing is done.")
    lines.append("Do this:")
    for n, st in enumerate(plan.steps, 1):
        if st.action == "shed":
            gain = f" (battery lasts {st.detail['battery_gain_h']:.1f} h longer)" if st.detail["battery_gain_h"] >= 0.1 else ""
            lines.append(f"{n}. During the cut, switch off: {', '.join(plan.shed)}{gain}")
        elif st.action == "prechill":
            gain = "" if st.detail["generator_h"] in (None, 0.0) else f" (cuts generator time to {st.detail['generator_h']:.1f} h)"
            lines.append(f"{n}. Set the cooler to {st.detail['to_c']:.0f}C from {_t(st.detail['from'])}{gain}")
        elif st.action == "generator":
            gs, ge = st.detail["window"]
            lines.append(f"{n}. Run the generator {_t(gs)}-{_t(ge)} only, not the whole cut "
                         f"(saves ~{plan.diesel_saved_l:.1f} L diesel)")
    if plan.final.safe:
        lines.append("Then milk stays safe.")
    else:
        lines.append("Milk is still at risk: ask the truck to come early or turn the evening milk into curd.")
    if plan.alternative and plan.alternative.outcome.safe:
        lines.append(f"Or: ask farmers to bring evening milk by {_t(plan.alternative.detail['evening_at'])}; "
                     "then no generator needed.")
    lines.append(f"If power is not back by {_t(e)}, run the generator until it is.")
    return "\n".join(lines)
