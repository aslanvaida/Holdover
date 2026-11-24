"""Load and input forecasts for one day, reusing the campus-energy-forecaster quantile model unchanged."""
import numpy as np
import pandas as pd

from campus_energy_forecaster.forecast import QuantileForecaster

from .centre import OPTIONAL_LOADS


def fit_load_models(meter: pd.DataFrame, train_end, loads=OPTIONAL_LOADS + ("cooler",)) -> dict[str, QuantileForecaster]:
    """One P10/P50/P90 model per circuit from calendar + weather ("expected" feature set: no recent-usage inputs, so it
    still works the day after an outage, when the meter has gaps). Hours on backup are NaN in the meter and are
    skipped."""
    train = meter.loc[:train_end]
    return {name: QuantileForecaster(name, "expected").fit(train[["temp", name]]) for name in loads}


def forecast_loads(models: dict[str, QuantileForecaster], weather: pd.Series, day, hours: int = 33) -> dict[str, pd.DataFrame]:
    """Forecast each circuit from ``day`` 00:00 for ``hours``, given the (forecast) weather. The day before is passed as
    context so the 24 h mean temperature feature is defined."""
    day = pd.Timestamp(day)
    ctx = weather.loc[day - pd.Timedelta(days=1): day + pd.Timedelta(hours=hours - 1)].to_frame("temp")
    out = {}
    for name, m in models.items():
        p = m.predict(ctx.assign(**{name: np.nan}))
        out[name] = p.loc[day:]
    return out


def weather_forecast(actual: pd.Series, day, hours: int = 33, sd: float = 1.5, seed: int = 0) -> pd.Series:
    """Stand-in for a day-ahead weather forecast: the simulated actual plus a day-level error and hourly noise
    (sd ~1.5 C, typical of day-ahead temperature forecasts). Replace with a real forecast API in deployment."""
    day = pd.Timestamp(day)
    rng = np.random.default_rng(seed + int(day.value // 10**9) % 100_000)
    seg = actual.loc[day - pd.Timedelta(days=1): day + pd.Timedelta(hours=hours - 1)].copy()
    future = seg.index >= day
    seg[future] = seg[future] + rng.normal(0, sd) + rng.normal(0, 0.5, future.sum())
    return seg.round(2)


def milk_forecast(sessions: pd.DataFrame, day, lookback: int = 7, stat: str = "mean") -> dict[str, float]:
    """Litres expected per session from the same session over the previous ``lookback`` days. ``stat="max"`` plans for
    the biggest recent collection rather than the typical one."""
    day = pd.Timestamp(day).normalize()
    past = sessions[(sessions["date"] < day) & (sessions["date"] >= day - pd.Timedelta(days=lookback))]
    return past.groupby("session")["litres"].agg(stat).round(0).to_dict()
