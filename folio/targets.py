"""Target-price tools: scenario math, technical levels, volatility-based ranges."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .indicators import TRADING_DAYS, annualized_vol

CASES = ("bear", "base", "bull")


def scenario_table(scenarios: dict, prices: dict[str, float]) -> pd.DataFrame:
    """Rows: ticker x case with target price and upside vs current price."""
    rows = []
    for ticker, cases in scenarios.items():
        px = prices.get(ticker, math.nan)
        for case in CASES:
            c = cases.get(case)
            if not c:
                continue
            rows.append({
                "ticker": ticker,
                "case": case,
                "target": float(c["price"]),
                "upside": float(c["price"]) / px - 1 if px else math.nan,
                "rationale": c.get("rationale", ""),
            })
    return pd.DataFrame(rows)


def scenario_portfolio_values(positions: pd.DataFrame, scenarios: dict, eurusd: float) -> dict[str, float]:
    """Portfolio EUR value if every holding hits its bear / base / bull target (FX held constant).

    A holding with no scenario keeps its current value.
    """
    out = {}
    for case in CASES:
        total = 0.0
        for _, p in positions.iterrows():
            target = scenarios.get(p["ticker"], {}).get(case, {}).get("price")
            if target is None:
                total += p["value_eur"]
                continue
            local = p["quantity"] * float(target)
            total += local / eurusd if p["currency"] == "USD" else local
        out[case] = total
    return out


def break_even_move(price: float, avg_cost: float) -> float:
    """Price change needed to get back to cost basis."""
    return avg_cost / price - 1 if price else math.nan


def swing_points(high: pd.Series, low: pd.Series, order: int = 5) -> tuple[list[float], list[float]]:
    """Local maxima of `high` / minima of `low` with `order` bars on each side."""
    highs, lows = [], []
    h, l = high.values, low.values
    for i in range(order, len(h) - order):
        if h[i] == max(h[i - order:i + order + 1]):
            highs.append(float(h[i]))
        if l[i] == min(l[i - order:i + order + 1]):
            lows.append(float(l[i]))
    return highs, lows


def cluster_levels(points: list[float], tolerance: float = 0.03) -> list[tuple[float, int]]:
    """Group nearby price points into levels. Returns (level, touches), strongest first."""
    if not points:
        return []
    pts = sorted(points)
    clusters: list[list[float]] = [[pts[0]]]
    for p in pts[1:]:
        if p <= np.mean(clusters[-1]) * (1 + tolerance):
            clusters[-1].append(p)
        else:
            clusters.append([p])
    levels = [(float(np.mean(c)), len(c)) for c in clusters]
    return sorted(levels, key=lambda x: -x[1])


def support_resistance(ohlc: pd.DataFrame, n: int = 2, lookback: int = TRADING_DAYS) -> dict[str, list[float]]:
    """Nearest `n` support levels below and resistance levels above the last close."""
    df = ohlc.dropna().tail(lookback)
    if len(df) < 20:
        return {"support": [], "resistance": []}
    last = float(df["Close"].iloc[-1])
    highs, lows = swing_points(df["High"], df["Low"])
    levels = cluster_levels(highs + lows, tolerance=0.05)
    support = sorted([lv for lv, _ in levels if lv < last * 0.97], reverse=True)[:n]
    resistance = sorted([lv for lv, _ in levels if lv > last * 1.03])[:n]
    return {"support": support, "resistance": resistance}


def vol_range(price: float, vol: float, months: int, z: float = 1.0) -> tuple[float, float]:
    """Log-normal +/- z-sigma price range over `months` given annualized `vol` (zero drift)."""
    if math.isnan(vol) or math.isnan(price):
        return (math.nan, math.nan)
    s = vol * math.sqrt(months / 12)
    return (price * math.exp(-z * s), price * math.exp(z * s))


def expected_ranges(close: pd.Series, horizons=(3, 6, 12)) -> pd.DataFrame:
    """1-sigma (~68%) and 2-sigma (~95%) ranges using 1-year realized volatility."""
    close = close.dropna()
    price = float(close.iloc[-1])
    vol = annualized_vol(close, TRADING_DAYS)
    rows = []
    for m in horizons:
        lo1, hi1 = vol_range(price, vol, m, 1)
        lo2, hi2 = vol_range(price, vol, m, 2)
        rows.append({"horizon": f"{m}m", "months": m, "low_2s": lo2, "low_1s": lo1, "high_1s": hi1, "high_2s": hi2})
    return pd.DataFrame(rows)


def prob_above(price: float, target: float, vol: float, months: int) -> float:
    """Zero-drift log-normal probability of finishing above `target` in `months`."""
    if any(math.isnan(x) for x in (price, target, vol)) or vol <= 0 or target <= 0:
        return math.nan
    s = vol * math.sqrt(months / 12)
    d = (math.log(price / target) - 0.5 * s * s) / s
    return 0.5 * (1 + math.erf(d / math.sqrt(2)))
