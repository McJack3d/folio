"""Load holdings and scenario files from the repo root."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Holding:
    ticker: str
    name: str
    quantity: float
    avg_cost: float
    currency: str
    theme: str = ""
    purchase_fx: float | None = None  # EUR/USD at purchase, for USD holdings


def load_holdings(path: Path | None = None) -> list[Holding]:
    data = yaml.safe_load((path or ROOT / "holdings.yaml").read_text())
    return [
        Holding(
            ticker=h["ticker"],
            name=h.get("name", h["ticker"]),
            quantity=float(h["quantity"]),
            avg_cost=float(h["avg_cost"]),
            currency=h.get("currency", "EUR").upper(),
            theme=h.get("theme", ""),
            purchase_fx=float(h["purchase_fx"]) if h.get("purchase_fx") else None,
        )
        for h in data["holdings"]
    ]


def load_scenarios(path: Path | None = None) -> dict:
    """Return {"horizon_months": int, "scenarios": {ticker: {case: {price, rationale}}}}."""
    data = yaml.safe_load((path or ROOT / "scenarios.yaml").read_text())
    data.setdefault("horizon_months", 12)
    data.setdefault("scenarios", {})
    return data
