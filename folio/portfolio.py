"""Portfolio valuation in the base currency (EUR)."""
from __future__ import annotations

import math

import pandas as pd

from .config import Holding


def to_eur(amount: float, currency: str, eurusd: float) -> float:
    """Convert an amount to EUR. `eurusd` is USD per 1 EUR (e.g. 1.14)."""
    if currency == "EUR":
        return amount
    if currency == "USD":
        return amount / eurusd
    raise ValueError(f"Unsupported currency {currency}")


def position_rows(holdings: list[Holding], prices: dict[str, float], prev_close: dict[str, float],
                  eurusd: float, eurusd_prev: float | None = None) -> pd.DataFrame:
    """One row per holding with market value, cost and P&L in EUR.

    P&L decomposition for USD holdings with a known `purchase_fx`:
      total EUR P&L = stock effect (price move, at purchase FX) + FX effect (currency move on current value).
    """
    eurusd_prev = eurusd_prev or eurusd
    rows = []
    for h in holdings:
        px = prices.get(h.ticker, math.nan)
        prev = prev_close.get(h.ticker, math.nan)
        value_local = h.quantity * px
        cost_local = h.quantity * h.avg_cost
        value_eur = to_eur(value_local, h.currency, eurusd)
        fx_cost = h.purchase_fx if (h.currency == "USD" and h.purchase_fx) else eurusd
        cost_eur = to_eur(cost_local, h.currency, fx_cost)
        pnl_eur = value_eur - cost_eur
        if h.currency == "USD" and h.purchase_fx:
            stock_effect = (value_local - cost_local) / h.purchase_fx
            fx_effect = pnl_eur - stock_effect
        else:
            stock_effect, fx_effect = pnl_eur, 0.0
        prev_value_eur = to_eur(h.quantity * prev, h.currency, eurusd_prev)
        rows.append({
            "ticker": h.ticker,
            "name": h.name,
            "theme": h.theme,
            "currency": h.currency,
            "quantity": h.quantity,
            "avg_cost": h.avg_cost,
            "price": px,
            "value_local": value_local,
            "value_eur": value_eur,
            "cost_eur": cost_eur,
            "pnl_eur": pnl_eur,
            "pnl_pct": pnl_eur / cost_eur if cost_eur else math.nan,
            "pnl_local_pct": px / h.avg_cost - 1 if h.avg_cost else math.nan,
            "stock_effect_eur": stock_effect,
            "fx_effect_eur": fx_effect,
            "day_change_eur": value_eur - prev_value_eur,
            "day_change_pct": px / prev - 1 if prev else math.nan,
            "fx_known": h.currency == "EUR" or bool(h.purchase_fx),
        })
    df = pd.DataFrame(rows)
    total = df["value_eur"].sum()
    df["weight"] = df["value_eur"] / total if total else math.nan
    return df


def totals(df: pd.DataFrame) -> dict:
    value = df["value_eur"].sum()
    cost = df["cost_eur"].sum()
    day = df["day_change_eur"].sum()
    return {
        "value_eur": value,
        "cost_eur": cost,
        "pnl_eur": value - cost,
        "pnl_pct": (value - cost) / cost if cost else math.nan,
        "day_change_eur": day,
        "day_change_pct": day / (value - day) if value - day else math.nan,
    }


def value_history(holdings: list[Holding], closes: pd.DataFrame, eurusd: pd.Series) -> pd.DataFrame:
    """Daily EUR value of the *current* quantities over the history in `closes`.

    `closes` has one column per ticker (local currency); `eurusd` is USD per EUR by date.
    Returns a frame with one EUR column per ticker plus 'total'.
    """
    idx = closes.index.union(eurusd.index)
    closes = closes.reindex(idx).ffill()
    fx = eurusd.reindex(idx).ffill().bfill()
    out = pd.DataFrame(index=idx)
    for h in holdings:
        if h.ticker not in closes:
            continue
        local = closes[h.ticker] * h.quantity
        out[h.ticker] = local / fx if h.currency == "USD" else local
    out = out.dropna(how="any")
    out["total"] = out.sum(axis=1)
    return out


def to_eur_series(close: pd.Series, currency: str, eurusd: pd.Series) -> pd.Series:
    if currency == "EUR":
        return close
    fx = eurusd.reindex(close.index.union(eurusd.index)).ffill().reindex(close.index)
    return close / fx


def index_to_100(s: pd.Series) -> pd.Series:
    s = s.dropna()
    return s / s.iloc[0] * 100 if len(s) else s
