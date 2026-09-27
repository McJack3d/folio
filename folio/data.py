"""Market data from Yahoo Finance (via yfinance), cached for the Streamlit session."""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st
import yfinance as yf

PRICE_TTL = 15 * 60  # seconds


@st.cache_data(ttl=PRICE_TTL, show_spinner=False)
def history(tickers: tuple[str, ...], period: str = "2y") -> dict[str, pd.DataFrame]:
    """Daily OHLCV per ticker (tz-naive index). Missing tickers are omitted."""
    raw = yf.download(list(tickers), period=period, interval="1d", auto_adjust=True,
                      group_by="ticker", progress=False, threads=True)
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        try:
            df = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
        except KeyError:
            continue
        df = df.dropna(subset=["Close"])
        if df.empty:
            continue
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        out[t] = df[~df.index.duplicated(keep="last")]
    return out


def closes(hist: dict[str, pd.DataFrame], tickers=None) -> pd.DataFrame:
    tickers = tickers or list(hist)
    return pd.DataFrame({t: hist[t]["Close"] for t in tickers if t in hist})


def last_and_prev(hist: dict[str, pd.DataFrame]) -> tuple[dict[str, float], dict[str, float]]:
    last, prev = {}, {}
    for t, df in hist.items():
        c = df["Close"].dropna()
        last[t] = float(c.iloc[-1]) if len(c) else math.nan
        prev[t] = float(c.iloc[-2]) if len(c) > 1 else last[t]
    return last, prev


def last_update(hist: dict[str, pd.DataFrame]) -> pd.Timestamp | None:
    dates = [df.index[-1] for df in hist.values() if len(df)]
    return max(dates) if dates else None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def info(ticker: str) -> dict:
    """Selected fundamentals; empty dict on failure."""
    keys = ["marketCap", "beta", "shortPercentOfFloat", "trailingPE", "forwardPE", "dividendYield",
            "totalRevenue", "revenueGrowth", "sector", "industry", "longBusinessSummary"]
    try:
        i = yf.Ticker(ticker).info or {}
    except Exception:
        return {}
    return {k: i.get(k) for k in keys}


@st.cache_data(ttl=30 * 60, show_spinner=False)
def news(ticker: str, limit: int = 10) -> list[dict]:
    """Recent Yahoo Finance headlines: title, summary, publisher, url, published (UTC)."""
    try:
        items = yf.Ticker(ticker).news or []
    except Exception:
        return []
    out = []
    for it in items[:limit]:
        c = it.get("content", it)
        url = (c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url") or c.get("link")
        out.append({
            "title": c.get("title", ""),
            "summary": c.get("summary") or c.get("description") or "",
            "publisher": (c.get("provider") or {}).get("displayName") or c.get("publisher", ""),
            "url": url,
            "published": pd.to_datetime(c.get("pubDate") or c.get("providerPublishTime"), utc=True, errors="coerce",
                                        unit=None if c.get("pubDate") else "s"),
        })
    return out
