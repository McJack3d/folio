"""Broad-market and nuclear-sector instruments, plus the composite mood scores."""
from __future__ import annotations

import math

import pandas as pd
import requests
import streamlit as st

from .indicators import fear_greed_to_score, technical_score, vix_to_score, weighted_mean

INDICES = {
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq Composite",
    "^STOXX50E": "Euro Stoxx 50",
    "^GDAXI": "DAX",
}
VIX = "^VIX"
FX = "EURUSD=X"

SECTOR_ETFS = {
    "URA": "Global X Uranium ETF",
    "URNM": "Sprott Uranium Miners ETF",
    "NLR": "VanEck Uranium & Nuclear ETF",
}
URANIUM_PROXY = {"SRUUF": "Sprott Physical Uranium Trust (spot U3O8 proxy)"}
PEERS = {
    "CCJ": "Cameco",
    "OKLO": "Oklo",
    "NNE": "Nano Nuclear Energy",
    "BWXT": "BWX Technologies",
    "CEG": "Constellation Energy",
    "UEC": "Uranium Energy Corp",
    "GEV": "GE Vernova",
}

ALL_MARKET = (*INDICES, VIX, FX, *SECTOR_ETFS, *URANIUM_PROXY, *PEERS)

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://edition.cnn.com/",
    "Origin": "https://edition.cnn.com",
}


@st.cache_data(ttl=60 * 60, show_spinner=False)
def fear_greed() -> dict | None:
    """CNN Fear & Greed index: score, rating, prior readings and a history series. None on failure."""
    try:
        r = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                         headers=_BROWSER_HEADERS, timeout=10)
        r.raise_for_status()
        d = r.json()
    except Exception:
        return None
    fg = d.get("fear_and_greed", {})
    hist = d.get("fear_and_greed_historical", {}).get("data", [])
    series = pd.Series({pd.to_datetime(p["x"], unit="ms").normalize(): p["y"] for p in hist}, dtype=float)
    return {
        "score": fg.get("score"),
        "rating": fg.get("rating", ""),
        "previous_close": fg.get("previous_close"),
        "previous_1_week": fg.get("previous_1_week"),
        "previous_1_month": fg.get("previous_1_month"),
        "previous_1_year": fg.get("previous_1_year"),
        "history": series.sort_index(),
    }


def market_mood(hist: dict[str, pd.DataFrame], fg: dict | None) -> dict:
    """Composite broad-market score in [-100, 100] with its components."""
    comps: dict[str, float] = {}
    if fg and fg.get("score") is not None:
        comps["CNN Fear & Greed"] = fear_greed_to_score(float(fg["score"]))
    if VIX in hist:
        comps["VIX (volatility)"] = vix_to_score(float(hist[VIX]["Close"].iloc[-1]))
    for t, name in INDICES.items():
        if t in hist:
            comps[f"{name} trend"] = technical_score(hist[t]["Close"])
    weights = {k: (2.0 if k.startswith("CNN") else 1.5 if k.startswith("VIX") else 1.0) for k in comps}
    score = weighted_mean(list(comps.values()), [weights[k] for k in comps])
    return {"score": score, "components": comps}


def sector_mood(hist: dict[str, pd.DataFrame]) -> dict:
    """Composite nuclear-sector score from sector ETFs, the uranium proxy and peers."""
    comps: dict[str, float] = {}
    for group, w in ((SECTOR_ETFS, 1.5), (URANIUM_PROXY, 2.0), (PEERS, 0.5)):
        for t, name in group.items():
            if t in hist:
                comps[name] = (technical_score(hist[t]["Close"]), w)
    score = weighted_mean([v for v, _ in comps.values()], [w for _, w in comps.values()])
    return {"score": score, "components": {k: v for k, (v, _) in comps.items()}}


def beta_corr(asset: pd.Series, bench: pd.Series, days: int = 252) -> tuple[float, float]:
    """Beta and correlation of daily returns over the last `days`."""
    df = pd.concat([asset, bench], axis=1).dropna().pct_change().dropna().tail(days)
    if len(df) < 30:
        return math.nan, math.nan
    cov = df.cov().iloc[0, 1]
    return float(cov / df.iloc[:, 1].var()), float(df.corr().iloc[0, 1])
