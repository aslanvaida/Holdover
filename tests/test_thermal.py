import numpy as np
import pandas as pd
import pytest

from campus_energy_forecaster.outage import Backup
from holdover.centre import Centre
from holdover.centre import Generator
from holdover.thermal import KJ_PER_K_PER_L, STEP, Scenario, simulate, summarise

T0 = pd.Timestamp("2026-06-01")
IDX = pd.date_range(T0, periods=48, freq="h")


def amb(c=35.0):
    return pd.Series(c, index=IDX)


def no_loads(kw=0.0):
    return pd.DataFrame({"lights": kw}, index=IDX)


def test_unpowered_tank_warms_like_newtons_law():
    c = Centre()
    f = simulate(c, Backup(0.0), T0, 10, amb(), no_loads(), Scenario([], outages=[(T0, T0 + pd.Timedelta(hours=10))]),
                 tank_c=4.0, tank_l=500)
    tau_h = 500 * KJ_PER_K_PER_L / (c.ua_w_per_k / 1000) / 3600
    expected = 35 - 31 * np.exp(-10 / tau_h)
    assert f["tank_c"].iloc[-1] == pytest.approx(expected, abs=0.05)


def test_mixing_warm_milk():
    c = Centre()
    f = simulate(c, Backup(0.0), T0, 0.1, amb(), no_loads(), Scenario([(T0, 500.0)], outages=[(T0, T0 + pd.Timedelta(hours=1))]),
                 tank_c=4.0, tank_l=500)
    assert f["tank_c"].iloc[0] == pytest.approx((4 + 35) / 2, abs=0.05)


def test_grid_chills_fresh_milk_within_window():
    f = simulate(Centre(), Backup(5.0), T0, 6, amb(), no_loads(), Scenario([(T0, 450.0)]), tank_l=0)
    assert not f["unsafe"].any() and f["tank_c"].iloc[-1] == pytest.approx(4.0, abs=0.01)


def test_shedding_extends_battery_and_generator_counts_diesel():
    c, b, g = Centre(), Backup(4.0, 1.0, 1.0), Generator()
    cut = [(T0, T0 + pd.Timedelta(hours=8))]
    base = dict(deliveries=[], outages=cut)
    allon = summarise(simulate(c, b, T0, 12, amb(), no_loads(0.5), Scenario(**base), tank_l=500), T0, g)
    shed = summarise(simulate(c, b, T0, 12, amb(), no_loads(0.5), Scenario(**base, keep_on_battery=()), tank_l=500), T0, g)
    assert shed.battery_hours is None or shed.battery_hours > allon.battery_hours
    gen = summarise(simulate(c, b, T0, 12, amb(), no_loads(0.5), Scenario(**base, generator=[(T0, T0 + pd.Timedelta(hours=2))]),
                             tank_l=500), T0, g)
    assert gen.diesel_l == pytest.approx(2 * g.litres_per_hour)


def test_prechill_lowers_temperature_before_cut():
    s = T0 + pd.Timedelta(hours=6)
    f = simulate(Centre(), Backup(0.0), T0, 6, amb(), no_loads(), Scenario([], prechill=(T0, s)), tank_c=4.0, tank_l=800)
    assert f["tank_c"].iloc[-1] == pytest.approx(Centre().prechill_c, abs=0.05)


def test_unsafe_only_after_chill_window():
    c = Centre()
    f = simulate(c, Backup(0.0), T0, 5, amb(), no_loads(), Scenario([(T0, 400.0)], outages=[(T0, T0 + pd.Timedelta(hours=5))]))
    first = f.index[f["unsafe"]][0]
    assert first + STEP - T0 > pd.Timedelta(hours=c.chill_window_h)   # rows hold the state at the end of each step
