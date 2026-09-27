import math

import numpy as np
import pandas as pd
import pytest

from folio.config import Holding, load_holdings, load_scenarios
from folio.indicators import label_score, rsi, technical_score, vix_to_score, weighted_mean
from folio.portfolio import position_rows, to_eur, totals, value_history
from folio.targets import (break_even_move, prob_above, scenario_portfolio_values, scenario_table,
                           support_resistance, vol_range)


def series(values, start="2025-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


HOLDINGS = [
    Holding("AAA", "Alpha", 10, 100.0, "USD"),
    Holding("BBB", "Beta", 20, 50.0, "EUR"),
    Holding("CCC", "Gamma", 5, 10.0, "USD", purchase_fx=1.0),
]


def test_repo_files_load():
    hs = load_holdings()
    assert {h.ticker for h in hs} == {"SMR", "LEU", "URNU.DE", "BHP1.F"}
    sc = load_scenarios()["scenarios"]
    for h in hs:
        assert sc[h.ticker]["bear"]["price"] < sc[h.ticker]["base"]["price"] < sc[h.ticker]["bull"]["price"]


def test_to_eur():
    assert to_eur(110, "USD", 1.10) == pytest.approx(100)
    assert to_eur(5, "EUR", 1.10) == 5
    with pytest.raises(ValueError):
        to_eur(1, "GBP", 1.1)


def test_position_rows_and_totals():
    prices = {"AAA": 110.0, "BBB": 40.0, "CCC": 12.0}
    df = position_rows(HOLDINGS, prices, prices, eurusd=1.25).set_index("ticker")
    # USD without purchase_fx: cost at today's FX -> P&L% equals local P&L%
    assert df.loc["AAA", "value_eur"] == pytest.approx(1100 / 1.25)
    assert df.loc["AAA", "pnl_pct"] == pytest.approx(0.10)
    assert df.loc["BBB", "pnl_eur"] == pytest.approx(-200)
    # USD with purchase_fx=1.0: value 60/1.25=48, cost 50 -> -2 = +10 stock effect, -12 FX effect
    assert df.loc["CCC", "pnl_eur"] == pytest.approx(-2)
    assert df.loc["CCC", "stock_effect_eur"] == pytest.approx(10)
    assert df.loc["CCC", "fx_effect_eur"] == pytest.approx(-12)
    assert df["weight"].sum() == pytest.approx(1)
    t = totals(df.reset_index())
    assert t["pnl_eur"] == pytest.approx(t["value_eur"] - t["cost_eur"])
    assert t["day_change_eur"] == pytest.approx(0)


def test_value_history_converts_usd():
    closes = pd.DataFrame({"AAA": series([100, 110]), "BBB": series([50, 50]), "CCC": series([10, 10])})
    fx = series([1.0, 1.1])
    vh = value_history(HOLDINGS, closes, fx)
    assert vh["AAA"].iloc[-1] == pytest.approx(1100 / 1.1)
    assert vh["total"].iloc[0] == pytest.approx(1000 + 1000 + 50)


def test_rsi_extremes():
    assert rsi(series(np.arange(1, 40))).iloc[-1] == pytest.approx(100)
    assert rsi(series(np.arange(40, 1, -1))).iloc[-1] == pytest.approx(0, abs=1e-6)


def test_technical_score_direction():
    up = series(100 * np.exp(np.linspace(0, 0.8, 300)))
    down = series(100 * np.exp(np.linspace(0, -0.8, 300)))
    assert technical_score(up) > 50
    assert technical_score(down) < -50
    assert -100 <= technical_score(up) <= 100


def test_labels_and_vix():
    assert label_score(60) == "Strongly bullish"
    assert label_score(0) == "Neutral"
    assert label_score(-30) == "Bearish"
    assert vix_to_score(20) == 0
    assert vix_to_score(12) == pytest.approx(100)
    assert vix_to_score(40) == pytest.approx(-100)


def test_weighted_mean_skips_nan():
    assert weighted_mean([10, math.nan, 30], [1, 5, 1]) == pytest.approx(20)
    assert math.isnan(weighted_mean([math.nan], [1]))


def test_scenarios():
    scen = {"AAA": {"bear": {"price": 80}, "base": {"price": 120}, "bull": {"price": 200}}}
    tab = scenario_table(scen, {"AAA": 100})
    assert tab.set_index("case").loc["bull", "upside"] == pytest.approx(1.0)
    pos = position_rows(HOLDINGS[:2], {"AAA": 100, "BBB": 50}, {"AAA": 100, "BBB": 50}, eurusd=1.0)
    pv = scenario_portfolio_values(pos, scen, eurusd=1.0)
    assert pv["bear"] == pytest.approx(800 + 1000)  # BBB has no scenario -> unchanged
    assert pv["bull"] == pytest.approx(2000 + 1000)


def test_break_even_and_vol_math():
    assert break_even_move(8, 10) == pytest.approx(0.25)
    lo, hi = vol_range(100, 0.5, 12, 1)
    assert lo == pytest.approx(100 * math.exp(-0.5)) and hi == pytest.approx(100 * math.exp(0.5))
    assert prob_above(100, 100, 0.5, 12) < 0.5  # zero-drift lognormal: median below spot
    assert prob_above(100, 1, 0.5, 12) > 0.99


def test_support_resistance_finds_levels():
    # oscillate between ~90 and ~110, end at 100
    x = np.linspace(0, 8 * np.pi, 240)
    close = series(100 + 10 * np.sin(x))
    ohlc = pd.DataFrame({"High": close + 0.5, "Low": close - 0.5, "Close": close})
    ohlc.iloc[-1] = [100.5, 99.5, 100]
    lv = support_resistance(ohlc)
    assert lv["support"] and lv["support"][0] == pytest.approx(89.5, abs=1.5)
    assert lv["resistance"] and lv["resistance"][0] == pytest.approx(110.5, abs=1.5)
