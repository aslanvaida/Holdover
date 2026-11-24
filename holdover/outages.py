"""When will the power go, and for how long? From the published schedule and the centre's own outage history."""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class OutageForecast:
    start: pd.Timestamp
    end_p50: pd.Timestamp
    end_p90: pd.Timestamp            # plan for this: the cut ends by then on 9 of 10 similar days
    probability: float
    basis: str

    @property
    def hours_p90(self) -> float:
        return (self.end_p90 - self.start) / pd.Timedelta(hours=1)


def predict_outage(day, history: list[tuple[pd.Timestamp, pd.Timestamp]], schedule, lookback_days: int = 56,
                   temp_max: float | None = None, history_temp_max: pd.Series | None = None) -> OutageForecast | None:
    """Expected cut on ``day``.

    If the schedule lists a slot for that weekday, the start is the scheduled start and the length comes from what
    actually happened in the same slot over the last ``lookback_days`` (cuts often overrun). If daily maximum
    temperatures are given, the overrun is scaled up for days hotter than the history, using the slope of overrun on
    temperature fitted to that history. Without a scheduled slot, it returns the most likely unscheduled cut only when
    one is more likely than not (otherwise None: no warning)."""
    day = pd.Timestamp(day).normalize()
    past = [(s, e) for s, e in history if day - pd.Timedelta(days=lookback_days) <= s < day]
    h = pd.Timedelta(hours=1)
    for wd, s_h, e_h in schedule:
        if day.day_of_week != wd:
            continue
        slots = [d for d in pd.date_range(day - pd.Timedelta(days=lookback_days), day - pd.Timedelta(days=1))
                 if d.day_of_week == wd]
        hits, overruns, tmax = 0, [], []
        for d in slots:
            sched_start = d + pd.Timedelta(hours=s_h)
            match = [(s, e) for s, e in past if abs(s - sched_start) <= pd.Timedelta(hours=1)]
            if match:
                hits += 1
                s, e = match[0]
                overruns.append((e - (d + pd.Timedelta(hours=e_h))) / h)
                if history_temp_max is not None:
                    tmax.append(float(history_temp_max.get(d, np.nan)))
        start = day + pd.Timedelta(hours=s_h)
        sched_end = day + pd.Timedelta(hours=e_h)
        if not overruns:
            return OutageForecast(start, sched_end, sched_end + h, 1.0 if not slots else 0.5, "schedule only")
        ov = np.array(overruns)
        shift = 0.0
        if temp_max is not None and len(tmax) >= 6 and np.isfinite(tmax).all():
            slope = np.polyfit(tmax, ov, 1)[0]
            shift = max(0.0, slope) * max(0.0, temp_max - float(np.mean(tmax)))
        p50, p90 = np.quantile(ov, 0.5) + shift, np.quantile(ov, 0.9) + shift
        return OutageForecast(start, (sched_end + pd.Timedelta(hours=p50)).round("15min"),
                              (sched_end + pd.Timedelta(hours=p90)).round("15min"),
                              round(hits / len(slots), 2), f"schedule + {hits} of {len(slots)} past slots")
    # unscheduled: most common start hour of past cuts
    if not past:
        return None
    starts = pd.Series([s.hour for s, _ in past])
    hour = int(starts.mode().iloc[0])
    p = float((starts == hour).sum()) / lookback_days
    if p < 0.5:
        return None
    lens = np.array([(e - s) / h for s, e in past if s.hour == hour])
    start = day + pd.Timedelta(hours=hour)
    return OutageForecast(start, start + pd.Timedelta(hours=float(np.quantile(lens, 0.5))),
                          start + pd.Timedelta(hours=float(np.quantile(lens, 0.9))), round(p, 2), "history only")
