"""Technical indicators and sentiment scoring. Pure functions over pandas Series."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(loss != 0, 100.0)


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window, min_periods=window).mean()


def pct_return(close: pd.Series, days: int) -> float:
    """Return over the last `days` trading sessions (nan if not enough history)."""
    close = close.dropna()
    if len(close) <= days:
        return math.nan
    return close.iloc[-1] / close.iloc[-1 - days] - 1


def ytd_return(close: pd.Series) -> float:
    close = close.dropna()
    if close.empty:
        return math.nan
    year = close.index[-1].year
    prior = close[close.index.year < year]
    if prior.empty:
        return math.nan
    return close.iloc[-1] / prior.iloc[-1] - 1


def annualized_vol(close: pd.Series, days: int = 63) -> float:
    rets = np.log(close.dropna()).diff().dropna().tail(days)
    if len(rets) < 10:
        return math.nan
    return float(rets.std() * math.sqrt(TRADING_DAYS))


def drawdown_from_high(close: pd.Series, days: int = TRADING_DAYS) -> float:
    window = close.dropna().tail(days)
    if window.empty:
        return math.nan
    return float(window.iloc[-1] / window.max() - 1)


def technical_summary(close: pd.Series) -> dict:
    """Headline technical stats for one instrument."""
    close = close.dropna()
    last = float(close.iloc[-1]) if len(close) else math.nan
    s50, s200 = sma(close, 50), sma(close, 200)
    r = rsi(close)
    return {
        "last": last,
        "rsi": float(r.iloc[-1]) if len(r.dropna()) else math.nan,
        "sma50": float(s50.iloc[-1]) if len(s50.dropna()) else math.nan,
        "sma200": float(s200.iloc[-1]) if len(s200.dropna()) else math.nan,
        "ret_1d": pct_return(close, 1),
        "ret_1w": pct_return(close, 5),
        "ret_1m": pct_return(close, 21),
        "ret_3m": pct_return(close, 63),
        "ret_ytd": ytd_return(close),
        "ret_1y": pct_return(close, TRADING_DAYS),
        "vol_3m": annualized_vol(close, 63),
        "drawdown_1y": drawdown_from_high(close),
        "high_52w": float(close.tail(TRADING_DAYS).max()) if len(close) else math.nan,
        "low_52w": float(close.tail(TRADING_DAYS).min()) if len(close) else math.nan,
    }


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def technical_score(close: pd.Series) -> float:
    """Bullish/bearish technical score in [-100, 100].

    Blends trend (price vs 50/200-day averages, golden/death cross), momentum
    (1m and 3m returns) and RSI. Positive = bullish.
    """
    t = technical_summary(close)
    parts: list[tuple[float, float]] = []  # (weight, signal in [-1, 1])
    last = t["last"]
    if not math.isnan(t["sma50"]):
        parts.append((0.2, _clip((last / t["sma50"] - 1) / 0.10)))
    if not math.isnan(t["sma200"]):
        parts.append((0.2, _clip((last / t["sma200"] - 1) / 0.20)))
        if not math.isnan(t["sma50"]):
            parts.append((0.1, 1.0 if t["sma50"] > t["sma200"] else -1.0))
    if not math.isnan(t["ret_1m"]):
        parts.append((0.2, _clip(t["ret_1m"] / 0.15)))
    if not math.isnan(t["ret_3m"]):
        parts.append((0.15, _clip(t["ret_3m"] / 0.30)))
    if not math.isnan(t["rsi"]):
        parts.append((0.15, _clip((t["rsi"] - 50) / 25)))
    if not parts:
        return math.nan
    total_w = sum(w for w, _ in parts)
    return 100 * sum(w * s for w, s in parts) / total_w


def label_score(score: float) -> str:
    if score is None or math.isnan(score):
        return "n/a"
    if score >= 50:
        return "Strongly bullish"
    if score >= 15:
        return "Bullish"
    if score > -15:
        return "Neutral"
    if score > -50:
        return "Bearish"
    return "Strongly bearish"


def fear_greed_to_score(fg: float) -> float:
    """Map CNN Fear & Greed (0..100) to [-100, 100]."""
    return (fg - 50) * 2


def vix_to_score(vix: float) -> float:
    """Low VIX = complacent/bullish, high VIX = fearful. 20 is neutral; ~12 -> +100, ~35 -> -100."""
    if vix <= 20:
        return _clip((20 - vix) / 8) * 100
    return -_clip((vix - 20) / 15) * 100


def weighted_mean(values: list[float], weights: list[float]) -> float:
    pairs = [(v, w) for v, w in zip(values, weights) if v is not None and not math.isnan(v) and w > 0]
    if not pairs:
        return math.nan
    return sum(v * w for v, w in pairs) / sum(w for _, w in pairs)


def signal_flags(t: dict, short_pct: float | None = None) -> list[tuple[str, str]]:
    """Plain-English flags from a technical_summary. Returns (kind, text); kind is bull / bear / info."""
    flags: list[tuple[str, str]] = []
    last, s50, s200, r = t["last"], t["sma50"], t["sma200"], t["rsi"]
    if not math.isnan(r):
        if r < 30:
            flags.append(("bull", f"Oversold (RSI {r:.0f}): selling looks stretched, bounces are common"))
        elif r > 70:
            flags.append(("bear", f"Overbought (RSI {r:.0f}): a pullback is common from here"))
    if not math.isnan(s200):
        above = last > s200
        flags.append(("bull" if above else "bear",
                      f"{'Above' if above else 'Below'} its 200-day average ({last / s200 - 1:+.0%}): long-term trend is "
                      f"{'up' if above else 'down'}"))
        if not math.isnan(s50):
            flags.append(("bull", "Golden cross: 50-day avg above 200-day") if s50 > s200
                         else ("bear", "Death cross: 50-day avg below 200-day"))
    if not math.isnan(t["drawdown_1y"]) and t["drawdown_1y"] < -0.4:
        flags.append(("info", f"{t['drawdown_1y']:.0%} below its 52-week high"))
    if not math.isnan(t["low_52w"]) and last <= t["low_52w"] * 1.08:
        flags.append(("bear", "Trading near its 52-week low"))
    if not math.isnan(t["vol_3m"]) and t["vol_3m"] > 0.8:
        flags.append(("info", f"Very volatile: {t['vol_3m']:.0%} annualized (3m)"))
    if short_pct and short_pct > 0.15:
        flags.append(("info", f"High short interest ({short_pct:.0%} of float): squeeze potential and bearish bets"))
    return flags
