"""Folio: nuclear-heavy portfolio dashboard. Run with `streamlit run app.py`."""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st
import yaml

from folio import charts, data, hype, market
from folio.config import load_holdings, load_scenarios
from folio.indicators import (TRADING_DAYS, annualized_vol, label_score, signal_flags, technical_score,
                              technical_summary, weighted_mean)
from folio.portfolio import index_to_100, position_rows, to_eur_series, totals, value_history
from folio.targets import (CASES, break_even_move, expected_ranges, prob_above, scenario_portfolio_values,
                           scenario_table, support_resistance)

st.set_page_config(page_title="Folio · Nuclear portfolio", page_icon="⚛️", layout="wide")

PERIODS = {"1M": 21, "3M": 63, "6M": 126, "YTD": None, "1Y": 252, "2Y": 504}


# ---------- formatting ----------
def eur(v: float, sign: bool = False) -> str:
    if v is None or math.isnan(v):
        return "–"
    return f"€{v:+,.0f}" if sign else f"€{v:,.0f}"


def pct(v: float, sign: bool = True, digits: int = 1) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v:+.{digits}%}" if sign else f"{v:.{digits}%}"


def score_str(v: float) -> str:
    return "–" if v is None or math.isnan(v) else f"{v:+.0f} · {label_score(v)}"


def slice_period(df, period: str):
    if period == "YTD":
        return df[df.index >= pd.Timestamp(pd.Timestamp.today().year, 1, 1)]
    return df.tail(PERIODS[period] + 1)


FLAG_ICON = {"bull": "🟦 ▲", "bear": "🟥 ▼", "info": "⬜ ●"}

# ---------- load ----------
holdings = load_holdings()
scen_cfg = load_scenarios()
scenarios = scen_cfg["scenarios"]
tickers = [h.ticker for h in holdings]
colors = charts.holding_color_map(tickers)

with st.sidebar:
    st.markdown("## ⚛️ Folio")
    period = st.segmented_control("Chart period", list(PERIODS), default="1Y") or "1Y"
    if st.button("🔄 Refresh data", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.caption("Prices refresh every 15 min, news & social every 30–60 min. "
               "Positions live in `holdings.yaml`, scenario targets in `scenarios.yaml`.")

with st.spinner("Fetching market data…"):
    hist = data.history(tuple(tickers) + market.ALL_MARKET, period="2y")

missing = [t for t in tickers if t not in hist]
if missing:
    st.error(f"No price data for {', '.join(missing)}. Check the Yahoo symbols in holdings.yaml.")
    st.stop()

last, prev = data.last_and_prev(hist)
fx_series = hist[market.FX]["Close"] if market.FX in hist else pd.Series(dtype=float)
eurusd = last.get(market.FX, float("nan"))
eurusd_prev = prev.get(market.FX, eurusd)

pos = position_rows(holdings, last, prev, eurusd, eurusd_prev)
tot = totals(pos)
vh = value_history(holdings, data.closes(hist, tickers), fx_series)

# ---------- signals ----------
fg = market.fear_greed()
mkt = market.market_mood(hist, fg)
sec = market.sector_mood(hist)
reddit = hype.reddit_mentions()

per_holding: dict[str, dict] = {}
for h in holdings:
    close = hist[h.ticker]["Close"]
    sym = hype.social_symbol(h.ticker)
    news_items = data.news(h.ticker) or data.news(sym)
    stw = hype.stocktwits(sym)
    rd = reddit.get(sym)
    tech = technical_score(close)
    news_s = hype.news_sentiment(news_items)
    social_s = stw["score"] if stw else math.nan
    per_holding[h.ticker] = {
        "summary": technical_summary(close),
        "tech": tech,
        "news": news_items,
        "news_score": news_s,
        "stocktwits": stw,
        "reddit": rd,
        "social_symbol": sym,
        "social_score": social_s,
        "hype": hype.hype_score(stw, rd),
        "signal": weighted_mean([tech, news_s, social_s], [0.6, 0.2, 0.2]),
    }

weights = dict(zip(pos["ticker"], pos["weight"]))
port_score = weighted_mean([per_holding[t]["signal"] for t in tickers], [weights[t] for t in tickers])
port_tech = weighted_mean([per_holding[t]["tech"] for t in tickers], [weights[t] for t in tickers])

# ---------- header ----------
st.title("⚛️ Folio")
upd = data.last_update(hist)
st.caption(f"Nuclear-heavy portfolio · values in EUR · EUR/USD {eurusd:.4f} · "
           f"latest market data {upd:%a %d %b %Y}" if upd is not None else "")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Portfolio value", eur(tot["value_eur"]),
          f"{eur(tot['day_change_eur'], True)} ({pct(tot['day_change_pct'])}) today")
k2.metric("Unrealized P&L", eur(tot["pnl_eur"], True), pct(tot["pnl_pct"]))
k3.metric("Your portfolio signal", f"{port_score:+.0f}", label_score(port_score), delta_color="off", delta_arrow="off")
k4.metric("Nuclear sector", f"{sec['score']:+.0f}", label_score(sec["score"]), delta_color="off", delta_arrow="off")
k5.metric("Broad market mood", f"{mkt['score']:+.0f}", label_score(mkt["score"]), delta_color="off", delta_arrow="off")


def verdict() -> str:
    gap = port_score - mkt["score"]
    lead = ("well ahead of" if gap > 30 else "ahead of" if gap > 10 else "in line with" if gap > -10
            else "behind" if gap > -30 else "far behind")
    fg_txt = f"CNN Fear & Greed reads **{fg['score']:.0f} ({fg['rating']})**. " if fg else ""
    return (f"{fg_txt}Your portfolio's signal is **{lead}** the broad market ({gap:+.0f} pts) and "
            f"{'stronger' if port_score > sec['score'] else 'weaker'} than the nuclear sector overall "
            f"({port_score - sec['score']:+.0f} pts). Signals blend trend, momentum, RSI, news tone and "
            f"StockTwits bull/bear tags on a −100 (bearish) to +100 (bullish) scale.")


st.info(verdict(), icon="🧭")

g1, g2, g3 = st.columns(3)
g1.plotly_chart(charts.gauge(mkt["score"], "Broad market"), width="stretch", config={"displayModeBar": False})
g2.plotly_chart(charts.gauge(sec["score"], "Nuclear sector"), width="stretch", config={"displayModeBar": False})
g3.plotly_chart(charts.gauge(port_score, "Your portfolio"), width="stretch", config={"displayModeBar": False})

tab_over, tab_mkt, tab_sec, tab_hold, tab_tgt, tab_news = st.tabs(
    ["📊 Overview", "🌍 Market vs portfolio", "☢️ Nuclear sector", "🔍 Holdings", "🎯 Targets", "📰 News & hype"])

# ---------- Overview ----------
with tab_over:
    c1, c2 = st.columns(2)
    c1.plotly_chart(charts.allocation_bar(pos, colors), width="stretch")
    c2.plotly_chart(charts.pnl_bar(pos), width="stretch")
    st.plotly_chart(charts.value_history(slice_period(vh, period), tot["cost_eur"], colors), width="stretch")
    st.caption("History shows what your *current* share counts would have been worth each day, "
               "not when you actually bought.")

    table = pos.assign(
        signal=[per_holding[t]["signal"] for t in pos["ticker"]],
        breakeven=[break_even_move(p, c) for p, c in zip(pos["price"], pos["avg_cost"])],
    )
    st.dataframe(
        table[["ticker", "name", "quantity", "avg_cost", "price", "currency", "day_change_pct", "value_eur",
               "pnl_eur", "pnl_pct", "breakeven", "weight", "signal"]],
        hide_index=True, width="stretch",
        column_config={
            "ticker": "Ticker", "name": "Name", "currency": "Ccy",
            "quantity": st.column_config.NumberColumn("Qty", format="%d"),
            "avg_cost": st.column_config.NumberColumn("Avg cost", format="%.2f"),
            "price": st.column_config.NumberColumn("Price", format="%.2f"),
            "day_change_pct": st.column_config.NumberColumn("Today", format="percent"),
            "value_eur": st.column_config.NumberColumn("Value", format="euro"),
            "pnl_eur": st.column_config.NumberColumn("P&L", format="euro"),
            "pnl_pct": st.column_config.NumberColumn("P&L %", format="percent"),
            "breakeven": st.column_config.NumberColumn("To break even", format="percent",
                                                       help="Price move needed to get back to your average cost"),
            "weight": st.column_config.ProgressColumn("Weight", format="percent", min_value=0, max_value=1),
            "signal": st.column_config.NumberColumn("Signal", format="%+.0f", help="−100 bearish … +100 bullish"),
        },
    )
    if not pos["fx_known"].all():
        st.caption("ℹ️ USD positions: EUR cost is computed at today's EUR/USD. Add `purchase_fx` in holdings.yaml "
                   "to split P&L into stock move vs currency move.")
    else:
        fx_split = pos[pos["currency"] == "USD"][["ticker", "stock_effect_eur", "fx_effect_eur"]]
        st.dataframe(fx_split, hide_index=True, column_config={
            "stock_effect_eur": st.column_config.NumberColumn("Stock move €", format="€%+.0f"),
            "fx_effect_eur": st.column_config.NumberColumn("Currency move €", format="€%+.0f")})

# ---------- Market vs portfolio ----------
with tab_mkt:
    bench = pd.DataFrame({"Your portfolio": vh["total"]})
    if "^GSPC" in hist:
        bench["S&P 500"] = to_eur_series(hist["^GSPC"]["Close"], "USD", fx_series)
    if "URA" in hist:
        bench["Uranium (URA)"] = to_eur_series(hist["URA"]["Close"], "USD", fx_series)
    if "^STOXX50E" in hist:
        bench["Euro Stoxx 50"] = hist["^STOXX50E"]["Close"]
    bench = slice_period(bench.ffill().dropna(), period)
    st.plotly_chart(charts.indexed_lines(bench.apply(index_to_100), charts.BENCH_COLORS,
                                         f"Your portfolio vs benchmarks, {period}, in EUR (start = 100)"),
                    width="stretch")

    rows = []
    for col in [c for c in bench.columns if c != "Your portfolio"]:
        b, c = market.beta_corr(bench["Your portfolio"], bench[col], days=len(bench))
        rows.append({"Benchmark": col, "Your return": bench["Your portfolio"].iloc[-1] / bench["Your portfolio"].iloc[0] - 1,
                     "Benchmark return": bench[col].iloc[-1] / bench[col].iloc[0] - 1, "Beta": b, "Correlation": c})
    rel = pd.DataFrame(rows)
    rel["Excess"] = rel["Your return"] - rel["Benchmark return"]
    st.dataframe(rel, hide_index=True, width="stretch", column_config={
        "Your return": st.column_config.NumberColumn(format="percent"),
        "Benchmark return": st.column_config.NumberColumn(format="percent"),
        "Excess": st.column_config.NumberColumn("Excess return", format="percent"),
        "Beta": st.column_config.NumberColumn(format="%.2f", help="1.5 = your portfolio moves ~1.5× the benchmark"),
        "Correlation": st.column_config.NumberColumn(format="%.2f")})

    c1, c2 = st.columns(2)
    compare = {"Broad market": mkt["score"], "Nuclear sector": sec["score"], "Your portfolio": port_score,
               "Your portfolio (technicals only)": port_tech}
    compare.update({f"· {t}": per_holding[t]["signal"] for t in tickers})
    c1.plotly_chart(charts.diverging_scores(compare, "Bullish / bearish: market vs you"), width="stretch")
    c2.plotly_chart(charts.diverging_scores(mkt["components"], "What drives the market mood"), width="stretch")

    if fg:
        f1, f2 = st.columns([1, 2])
        with f1:
            st.metric("CNN Fear & Greed", f"{fg['score']:.0f}", fg["rating"].title(), delta_color="off", delta_arrow="off")
            st.markdown(f"- Previous close: **{fg['previous_close']:.0f}**\n"
                        f"- 1 week ago: **{fg['previous_1_week']:.0f}**\n"
                        f"- 1 month ago: **{fg['previous_1_month']:.0f}**\n"
                        f"- 1 year ago: **{fg['previous_1_year']:.0f}**")
        if len(fg["history"]):
            f2.plotly_chart(charts.fear_greed_history(fg["history"]), width="stretch")
    else:
        st.caption("CNN Fear & Greed is unavailable right now; market mood uses VIX and index trends only.")

    idx_rows = []
    for t, name in {**market.INDICES, market.VIX: "VIX"}.items():
        if t in hist:
            s = technical_summary(hist[t]["Close"])
            idx_rows.append({"Index": name, "Level": s["last"], "1D": s["ret_1d"], "1M": s["ret_1m"],
                             "YTD": s["ret_ytd"], "vs 200-day": s["last"] / s["sma200"] - 1, "RSI": s["rsi"]})
    st.dataframe(pd.DataFrame(idx_rows), hide_index=True, width="stretch", column_config={
        "Level": st.column_config.NumberColumn(format="%.2f"),
        **{c: st.column_config.NumberColumn(format="percent") for c in ("1D", "1M", "YTD", "vs 200-day")},
        "RSI": st.column_config.NumberColumn(format="%.0f")})

# ---------- Nuclear sector ----------
with tab_sec:
    st.plotly_chart(charts.diverging_scores(sec["components"], "Nuclear sector: trend & momentum score per instrument"),
                    width="stretch")
    groups = [("Your holding", {h.ticker: h.name for h in holdings}), ("Uranium spot proxy", market.URANIUM_PROXY),
              ("Sector ETF", market.SECTOR_ETFS), ("Peer", market.PEERS)]
    rows = []
    for group, members in groups:
        for t, name in members.items():
            if t not in hist:
                continue
            s = technical_summary(hist[t]["Close"])
            rows.append({"Group": group, "Ticker": t, "Name": name, "Price": s["last"], "1D": s["ret_1d"],
                         "1W": s["ret_1w"], "1M": s["ret_1m"], "3M": s["ret_3m"], "YTD": s["ret_ytd"],
                         "1Y": s["ret_1y"], "From 52w high": s["drawdown_1y"], "RSI": s["rsi"],
                         "Score": technical_score(hist[t]["Close"])})
    sector_df = pd.DataFrame(rows)
    st.dataframe(sector_df, hide_index=True, width="stretch", height=560, column_config={
        "Price": st.column_config.NumberColumn(format="%.2f"),
        **{c: st.column_config.NumberColumn(format="percent") for c in ("1D", "1W", "1M", "3M", "YTD", "1Y", "From 52w high")},
        "RSI": st.column_config.NumberColumn(format="%.0f"),
        "Score": st.column_config.NumberColumn(format="%+.0f")})

    comp = {"Your portfolio": vh["total"]}
    for t in ("SRUUF", "URA", "CCJ", "OKLO"):
        if t in hist:
            comp[f"{t}"] = to_eur_series(hist[t]["Close"], "USD", fx_series)
    comp_df = slice_period(pd.DataFrame(comp).ffill().dropna(), period).apply(index_to_100)
    sector_colors = {"Your portfolio": "#9085e9", "SRUUF": "#008300", "URA": "#d55181", "CCJ": "#e66767", "OKLO": "#c3c2b7"}
    st.plotly_chart(charts.indexed_lines(comp_df, sector_colors,
                                         f"Your portfolio vs uranium & nuclear leaders, {period}, EUR (start = 100)"),
                    width="stretch")
    st.caption("SRUUF (Sprott Physical Uranium Trust) holds physical U3O8, so it is used as a live proxy for the uranium spot price.")

# ---------- Holdings ----------
with tab_hold:
    sub = st.tabs([f"{h.ticker} · {h.name}" for h in holdings])
    for h, tab in zip(holdings, sub):
        with tab:
            ph = per_holding[h.ticker]
            s = ph["summary"]
            row = pos.set_index("ticker").loc[h.ticker]
            fund = data.info(h.ticker)
            m = st.columns(6)
            m[0].metric("Price", f"{s['last']:,.2f} {h.currency}", pct(s["ret_1d"]))
            m[1].metric("Your P&L", eur(row["pnl_eur"], True), pct(row["pnl_local_pct"]))
            m[2].metric("To break even", pct(break_even_move(s["last"], h.avg_cost)))
            m[3].metric("Signal", f"{ph['signal']:+.0f}", label_score(ph["signal"]), delta_color="off", delta_arrow="off")
            m[4].metric("RSI (14)", f"{s['rsi']:.0f}")
            m[5].metric("From 52w high", pct(s["drawdown_1y"], digits=0))

            levels = support_resistance(hist[h.ticker])
            ohlc = slice_period(hist[h.ticker], period)
            st.plotly_chart(charts.price_chart(ohlc, h.ticker, colors[h.ticker], h.avg_cost, levels=levels,
                                               currency=h.currency), width="stretch")
            st.caption("Dotted green/red lines = nearest support/resistance from the last year of swing lows/highs.")

            c1, c2 = st.columns([3, 2])
            with c1:
                st.markdown("**Signals**")
                for kind, text in signal_flags(s, fund.get("shortPercentOfFloat")):
                    st.markdown(f"{FLAG_ICON[kind]} {text}")
            with c2:
                st.markdown("**Stats**")
                stats = {
                    "Returns 1W / 1M / 3M": f"{pct(s['ret_1w'])} / {pct(s['ret_1m'])} / {pct(s['ret_3m'])}",
                    "YTD / 1Y": f"{pct(s['ret_ytd'])} / {pct(s['ret_1y'])}",
                    "52-week range": f"{s['low_52w']:,.2f} – {s['high_52w']:,.2f}",
                    "Volatility (3m, annualized)": pct(s["vol_3m"], sign=False, digits=0),
                    "50 / 200-day avg": f"{s['sma50']:,.2f} / {s['sma200']:,.2f}",
                }
                if fund.get("marketCap"):
                    stats["Market cap"] = f"{fund['marketCap'] / 1e9:,.1f} bn"
                if fund.get("beta"):
                    stats["Beta"] = f"{fund['beta']:.2f}"
                if fund.get("shortPercentOfFloat"):
                    stats["Short interest"] = pct(fund["shortPercentOfFloat"], sign=False)
                if fund.get("forwardPE"):
                    stats["Forward P/E"] = f"{fund['forwardPE']:.1f}"
                if fund.get("dividendYield"):
                    stats["Dividend yield"] = f"{fund['dividendYield']:.2f}%"
                st.table(pd.Series(stats, name="").to_frame())
            if fund.get("longBusinessSummary"):
                with st.expander("About the company"):
                    st.write(fund["longBusinessSummary"])

# ---------- Targets ----------
with tab_tgt:
    horizon = int(scen_cfg.get("horizon_months", 12))
    st.markdown(f"**{horizon}-month bull / base / bear scenarios** from `scenarios.yaml`, cross-checked against "
                "technical levels and what the stock's own volatility says is plausible. Estimates, not advice.")

    with st.expander("✏️ Tweak targets for this session"):
        edit_rows = [{"ticker": t, "case": c, "price": scenarios.get(t, {}).get(c, {}).get("price"),
                      "rationale": scenarios.get(t, {}).get(c, {}).get("rationale", "")}
                     for t in tickers for c in CASES]
        edited = st.data_editor(pd.DataFrame(edit_rows), hide_index=True, width="stretch",
                                disabled=["ticker", "case"], key="scen_edit",
                                column_config={"price": st.column_config.NumberColumn(format="%.2f")})
        scenarios = {}
        for r in edited.to_dict("records"):
            if r["price"] is not None and not pd.isna(r["price"]):
                scenarios.setdefault(r["ticker"], {})[r["case"]] = {"price": float(r["price"]),
                                                                    "rationale": r["rationale"]}
        st.download_button("Download as scenarios.yaml", yaml.safe_dump(
            {"horizon_months": horizon, "scenarios": scenarios}, sort_keys=False, allow_unicode=True),
            file_name="scenarios.yaml", mime="text/yaml")
        st.caption("Edits last for this browser session. To keep them, commit the downloaded file to the repo.")

    scen = scenario_table(scenarios, last)
    pv = scenario_portfolio_values(pos, scenarios, eurusd)
    m = st.columns(4)
    m[0].metric("Today", eur(tot["value_eur"]), f"cost {eur(tot['cost_eur'])}", delta_color="off", delta_arrow="off")
    for col, case in zip(m[1:], CASES):
        col.metric(f"{case.title()} case", eur(pv[case]),
                   f"{pv[case] / tot['value_eur'] - 1:+.0%} · P&L {eur(pv[case] - tot['cost_eur'], True)}")

    be = {h.ticker: break_even_move(last[h.ticker], h.avg_cost) for h in holdings}
    st.plotly_chart(charts.scenario_dots(scen, be, colors), width="stretch")

    for h in holdings:
        close = hist[h.ticker]["Close"]
        cases = scenarios.get(h.ticker, {})
        targets = {c: cases[c]["price"] for c in CASES if c in cases}
        with st.expander(f"{h.ticker} · {h.name}: scenarios, volatility cone & levels", expanded=h is holdings[0]):
            c1, c2 = st.columns([3, 2])
            ranges = expected_ranges(close)
            with c1:
                st.plotly_chart(charts.cone_chart(close, ranges, colors[h.ticker], targets, h.avg_cost),
                                width="stretch", key=f"cone_{h.ticker}")
            with c2:
                vol = annualized_vol(close, TRADING_DAYS)
                rows = []
                for c in CASES:
                    if c in cases:
                        rows.append({"Case": c.title(), "Target": cases[c]["price"],
                                     "Upside": cases[c]["price"] / last[h.ticker] - 1,
                                     "Chance above": prob_above(last[h.ticker], cases[c]["price"], vol, horizon)})
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
                    "Target": st.column_config.NumberColumn(format="%.2f"),
                    "Upside": st.column_config.NumberColumn(format="percent"),
                    "Chance above": st.column_config.NumberColumn(
                        "Chance to end above", format="percent", help="Chance of finishing above the target if the stock keeps its "
                                               "1-year volatility and has no drift. A sanity check, not a forecast.")})
                lv = support_resistance(hist[h.ticker])
                st.markdown("**Technical levels** "
                            f"(price {last[h.ticker]:,.2f} {h.currency})\n\n"
                            f"- Resistance: {', '.join(f'{x:,.2f}' for x in lv['resistance']) or 'none nearby (price discovery)'}\n"
                            f"- Support: {', '.join(f'{x:,.2f}' for x in lv['support']) or 'none nearby'}\n"
                            f"- 1-year realized volatility: {vol:.0%}")
                rg = ranges.set_index("horizon")
                st.markdown("**Volatility ranges (~68%)**: " + " · ".join(
                    f"{k}: {r.low_1s:,.2f}–{r.high_1s:,.2f}" for k, r in rg.iterrows()))
            for c in CASES:
                if c in cases and cases[c].get("rationale"):
                    st.markdown(f"**{c.title()} ({cases[c]['price']:,.2f})**: {cases[c]['rationale']}")

# ---------- News & hype ----------
with tab_news:
    rows = []
    for h in holdings:
        ph = per_holding[h.ticker]
        stw, rd = ph["stocktwits"], ph["reddit"]
        rows.append({
            "Ticker": h.ticker, "Social symbol": ph["social_symbol"],
            "News tone": ph["news_score"],
            "StockTwits bull/bear": f"{stw['bullish']}🟦 / {stw['bearish']}🟥" if stw else "–",
            "StockTwits score": ph["social_score"],
            "Watchers": stw["watchers"] if stw else None,
            "Reddit mentions 24h": rd["mentions"] if rd else None,
            "Reddit rank": rd["rank"] if rd else None,
            "Hype meter": ph["hype"],
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
        "News tone": st.column_config.NumberColumn(format="%+.0f", help="VADER sentiment of recent headlines, −100…+100"),
        "StockTwits score": st.column_config.NumberColumn(format="%+.0f", help="(bullish − bearish) / tagged posts, last ~30 posts"),
        "Watchers": st.column_config.NumberColumn(format="%d"),
        "Reddit rank": st.column_config.NumberColumn(format="%d", help="Rank by mentions across Reddit investing subs "
                                                     "(ApeWisdom). Blank = not in the top ~1,000 most-discussed tickers today"),
        "Hype meter": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100,
                                                      help="Attention, not direction: crowd size + chatter growth"),
    })
    st.caption("URNU and BHP1 trade in Europe, so social data uses their closest US-listed twins (URNM, BHP).")

    for h in holdings:
        ph = per_holding[h.ticker]
        with st.expander(f"{h.ticker} · {h.name}: {len(ph['news'])} headlines, news tone {ph['news_score']:+.0f}"
                         if not math.isnan(ph["news_score"]) else f"{h.ticker} · {h.name}: no headlines",
                         expanded=h is holdings[0]):
            for n in ph["news"]:
                sc = hype.headline_score(f"{n['title']}. {n['summary']}")
                chip = "🟦" if sc > 0.15 else "🟥" if sc < -0.15 else "⬜"
                when = n["published"].strftime("%d %b %H:%M") if pd.notna(n["published"]) else ""
                st.markdown(f"{chip} [{n['title']}]({n['url']})  \n"
                            f"<span style='color:#898781;font-size:0.85em'>{n['publisher']} · {when} · tone {sc:+.2f}</span>",
                            unsafe_allow_html=True)
            stw = ph["stocktwits"]
            if stw and stw["latest"]:
                st.markdown("**Latest StockTwits posts**")
                for msg in stw["latest"][:5]:
                    tag = {"Bullish": "🟦 Bullish", "Bearish": "🟥 Bearish"}.get(msg["sentiment"], "⬜ untagged")
                    st.markdown(f"<span style='color:#898781;font-size:0.85em'>{tag}</span> {msg['body'][:220]}",
                                unsafe_allow_html=True)

st.divider()
st.caption("Data: Yahoo Finance (prices, news, fundamentals), CNN Fear & Greed, StockTwits, ApeWisdom (Reddit). "
           "Scores and targets are heuristic estimates for personal tracking, not investment advice.")
