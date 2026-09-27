"""News sentiment and social 'hype' signals: VADER on headlines, StockTwits, Reddit (via ApeWisdom)."""
from __future__ import annotations

import math

import requests
import streamlit as st
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_UA = {"User-Agent": "Mozilla/5.0 (compatible; folio-dashboard/1.0)"}
_vader = SentimentIntensityAnalyzer()

# Yahoo symbol -> symbol used by US social platforms
SOCIAL_SYMBOL = {"URNU.DE": "URNM", "BHP1.F": "BHP"}


def social_symbol(ticker: str) -> str:
    return SOCIAL_SYMBOL.get(ticker, ticker.split(".")[0])


def headline_score(text: str) -> float:
    """VADER compound score in [-1, 1]."""
    return _vader.polarity_scores(text or "")["compound"]


def news_sentiment(items: list[dict]) -> float:
    """Average headline+summary sentiment scaled to [-100, 100]."""
    scores = [headline_score(f"{i['title']}. {i['summary']}") for i in items if i.get("title")]
    return 100 * sum(scores) / len(scores) if scores else math.nan


@st.cache_data(ttl=30 * 60, show_spinner=False)
def stocktwits(symbol: str) -> dict | None:
    """Bull/bear tags on the latest ~30 StockTwits messages plus watchlist size."""
    try:
        r = requests.get(f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json", headers=_UA, timeout=10)
        r.raise_for_status()
        d = r.json()
    except Exception:
        return None
    msgs = d.get("messages", [])
    tags = [((m.get("entities") or {}).get("sentiment") or {}).get("basic") for m in msgs]
    bull, bear = tags.count("Bullish"), tags.count("Bearish")
    return {
        "watchers": (d.get("symbol") or {}).get("watchlist_count"),
        "messages": len(msgs),
        "bullish": bull,
        "bearish": bear,
        "score": 100 * (bull - bear) / (bull + bear) if bull + bear else math.nan,
        "latest": [{"body": m.get("body", ""), "created_at": m.get("created_at"),
                    "sentiment": t} for m, t in zip(msgs[:8], tags[:8])],
    }


@st.cache_data(ttl=60 * 60, show_spinner=False)
def reddit_mentions() -> dict[str, dict]:
    """Ticker -> {rank, mentions, mentions_24h_ago, upvotes} across Reddit investing subs (ApeWisdom)."""
    out: dict[str, dict] = {}
    for page in range(1, 11):
        try:
            r = requests.get(f"https://apewisdom.io/api/v1.0/filter/all-stocks/page/{page}", headers=_UA, timeout=10)
            r.raise_for_status()
            d = r.json()
        except Exception:
            break
        for row in d.get("results", []):
            out[row["ticker"]] = {
                "rank": row.get("rank"),
                "mentions": int(row.get("mentions") or 0),
                "mentions_24h_ago": int(row.get("mentions_24h_ago") or 0),
                "upvotes": int(row.get("upvotes") or 0),
            }
        if page >= int(d.get("pages") or 1):
            break
    return out


def hype_score(st_data: dict | None, reddit: dict | None) -> float:
    """Attention score in [0, 100]: social crowd size and chatter. Direction-free (hype != bullish)."""
    parts = []
    if reddit:
        parts.append(min(100, 25 * math.log10(1 + reddit["mentions"]) * 2))
        if reddit["mentions_24h_ago"]:
            growth = reddit["mentions"] / reddit["mentions_24h_ago"]
            parts.append(max(0, min(100, 50 + 50 * math.log2(growth))))
    if st_data and st_data.get("watchers"):
        parts.append(min(100, 20 * math.log10(st_data["watchers"])))
    return sum(parts) / len(parts) if parts else math.nan
