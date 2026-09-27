# ⚛️ Folio

A personal dashboard for a nuclear-heavy portfolio. Open it from a phone or laptop to see how the positions are doing in EUR, how bullish or bearish the market, the nuclear sector and the portfolio look, and where 12-month targets sit.

| Holding | Listing | Qty | Avg cost |
|---|---|---|---|
| NuScale Power | `SMR` (NYSE, USD) | 416 | 11.78 USD |
| Centrus Energy | `LEU` (NYSE American, USD) | 8 | 194.00 USD |
| Global X Uranium UCITS ETF | `URNU.DE` (Xetra, EUR) | 32 | 25.87 EUR |
| BHP Group | `BHP1.F` (Frankfurt, EUR) | 16 | 36.00 EUR |

## What's inside

- **Header**: portfolio value, today's change, unrealized P&L, and three gauges (broad market, nuclear sector, your portfolio) on a −100 (bearish) to +100 (bullish) scale, with a one-line verdict.
- **📊 Overview**: allocation, P&L per position, the value of your current positions over time against cost basis, and a positions table with the move needed to break even.
- **🌍 Market vs portfolio**: your portfolio against the S&P 500, uranium (URA) and Euro Stoxx 50 (all in EUR, start = 100), with beta, correlation and excess return. Also the drivers of market mood (CNN Fear & Greed, VIX, index trends), Fear & Greed history, and an index table.
- **☢️ Nuclear sector**: trend and momentum scores for the uranium spot proxy (Sprott Physical Uranium Trust), sector ETFs (URA, URNM, NLR) and peers (Cameco, Oklo, NuScale's rivals, Constellation…), plus a returns table and a relative-performance chart.
- **🔍 Holdings**: one page per stock with a price chart (50/200-day averages, your cost line, support and resistance), RSI, plain-English signals (oversold, death cross, high short interest…) and key stats.
- **🎯 Targets**: bull, base and bear 12-month scenarios with the reasoning behind each, the portfolio value in each scenario, the break-even marker, volatility cones (~68% and ~95% ranges at 3, 6 and 12 months), vol-implied odds of reaching each target, and technical levels. Targets can be tweaked in the app and downloaded as `scenarios.yaml`.
- **📰 News & hype**: Yahoo Finance headlines scored for tone, StockTwits bull/bear tags and watcher counts, Reddit mention rank (ApeWisdom), and a direction-free hype meter.

### How the scores work

Every score runs from −100 to +100.

- **Technical score** (`folio/indicators.py → technical_score`): price vs its 50- and 200-day averages, golden or death cross, 1-month and 3-month momentum, and RSI.
- **Holding signal**: 60% technical, 20% news tone, 20% StockTwits bull/bear ratio. When a source is missing, the remaining weights are rescaled.
- **Your portfolio**: the holding signals, weighted by position size.
- **Nuclear sector**: technical scores of the uranium proxy (×2), sector ETFs (×1.5) and peers (×0.5).
- **Broad market**: CNN Fear & Greed (×2), VIX (×1.5), and the trends of the S&P 500, Nasdaq, Euro Stoxx 50 and DAX.

These are heuristics for personal tracking, not investment advice.

## Updating your positions

- **Buy, sell or change your average cost:** edit `holdings.yaml` (on GitHub, click the file, then the ✏️ icon) and commit. The deployed app redeploys by itself.
- **Split EUR P&L into stock move vs currency move:** add `purchase_fx: 1.08` (the EUR/USD rate when you bought) to a USD holding.
- **Add a new holding:** append an entry with its Yahoo Finance symbol. Find the symbol on finance.yahoo.com, e.g. `CCJ`, `U-UN.TO` or `KAP.IL`. Supported currencies are EUR and USD.
- **Update scenario targets:** edit `scenarios.yaml`, or use *Targets → Tweak targets* in the app and commit the downloaded file.

## Put it online (free, about 5 minutes)

1. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub.
2. Click **Create app → Deploy a public app from GitHub**. Pick repo `McJack3d/folio`, branch `main`, main file `app.py`.
3. Click **Deploy**. You'll get a URL like `https://folio-xxxx.streamlit.app`. Bookmark it or add it to your phone's home screen.

The app sleeps after a few days without visits, and the first load after that takes about 30 seconds to wake up.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Tests (pure calculation code, no network):

```bash
pip install pytest
python -m pytest
```

## Data sources

- **Yahoo Finance** via `yfinance`: prices, FX, news and fundamentals. Cached for 15 minutes; press *Refresh data* in the sidebar to force an update.
- **CNN Fear & Greed**: the public data endpoint behind cnn.com/markets/fear-and-greed.
- **StockTwits**: public symbol stream (bull/bear tags on recent posts).
- **ApeWisdom**: Reddit mention counts.

If a source is down, the app still loads and the related score is computed from whatever is available.

## Project layout

```
app.py              Streamlit UI (tabs, tables, layout)
holdings.yaml       your positions
scenarios.yaml      bull/base/bear targets + rationale
folio/config.py     loads the YAML files
folio/data.py       Yahoo Finance fetchers (cached)
folio/market.py     indices, sector instruments, Fear & Greed, mood scores
folio/hype.py       news tone (VADER), StockTwits, Reddit mentions
folio/indicators.py RSI, moving averages, returns, scores, signal flags
folio/portfolio.py  EUR valuation, P&L, value history
folio/targets.py    scenarios, support/resistance, volatility ranges
folio/charts.py     Plotly figures
tests/              unit tests
```
