"""Plotly figures. Colours follow a validated dark-mode palette; each holding keeps its colour everywhere."""
from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Chart chrome (dark)
INK = "#ffffff"
INK_2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
AXIS = "#383835"
SURFACE = "#1a1a19"

# Categorical slots for holdings (validated adjacent-safe, dark surface)
HOLDING_COLORS = ["#3987e5", "#d95926", "#199e70", "#c98500"]
# Separate hues for portfolio-vs-benchmark charts so they never collide with holdings
BENCH_COLORS = {"Your portfolio": "#9085e9", "S&P 500": "#d55181", "Uranium (URA)": "#008300", "Euro Stoxx 50": "#e66767"}
# Diverging pair: bullish (blue) <-> bearish (red), neutral grey midpoint
BULL, BEAR, NEUTRAL = "#3987e5", "#e66767", "#383835"
GOOD, CRITICAL, WARNING = "#0ca30c", "#d03b3b", "#fab219"


def holding_color_map(tickers: list[str]) -> dict[str, str]:
    return {t: HOLDING_COLORS[i % len(HOLDING_COLORS)] for i, t in enumerate(tickers)}


def _base(fig: go.Figure, height: int = 360, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=36, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=INK_2, size=12),
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=AXIS, font=dict(color=INK)),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="left", x=0, font=dict(color=INK_2)),
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    return fig


def score_color(v: float) -> str:
    if v is None or math.isnan(v):
        return NEUTRAL
    return BULL if v >= 15 else BEAR if v <= -15 else "#898781"


def allocation_bar(pos: pd.DataFrame, colors: dict[str, str]) -> go.Figure:
    df = pos.sort_values("weight")
    fig = go.Figure(go.Bar(
        x=df["weight"] * 100, y=df["ticker"], orientation="h",
        marker=dict(color=[colors[t] for t in df["ticker"]], line=dict(color=SURFACE, width=2)),
        text=[f"{w:.0%} · €{v:,.0f}" for w, v in zip(df["weight"], df["value_eur"])],
        textposition="outside", textfont=dict(color=INK_2), cliponaxis=False,
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    fig = _base(fig, height=60 + 44 * len(df), legend=False)
    fig.update_layout(hovermode="closest", title=dict(text="Allocation", font=dict(color=INK, size=14)))
    fig.update_xaxes(ticksuffix="%", range=[0, max(df["weight"] * 100) * 1.45])
    return fig


def pnl_bar(pos: pd.DataFrame) -> go.Figure:
    df = pos.sort_values("pnl_eur")
    fig = go.Figure(go.Bar(
        x=df["pnl_eur"], y=df["ticker"], orientation="h",
        marker=dict(color=[GOOD if v >= 0 else CRITICAL for v in df["pnl_eur"]], line=dict(color=SURFACE, width=2)),
        text=[f"{'▲' if v >= 0 else '▼'} €{v:+,.0f} ({p:+.1%})" for v, p in zip(df["pnl_eur"], df["pnl_pct"])],
        textposition="auto", insidetextanchor="middle", textfont=dict(color=INK_2), cliponaxis=False,
        hovertemplate="%{y}: €%{x:,.0f}<extra></extra>",
    ))
    fig = _base(fig, height=60 + 44 * len(df), legend=False)
    lim = max(abs(df["pnl_eur"]).max(), 1) * 2.6
    fig.update_layout(hovermode="closest", title=dict(text="Unrealized P&L (EUR)", font=dict(color=INK, size=14)))
    fig.update_xaxes(range=[-lim, lim], tickprefix="€", zeroline=True, zerolinecolor=AXIS)
    return fig


def value_history(vh: pd.DataFrame, cost_eur: float, colors: dict[str, str]) -> go.Figure:
    fig = go.Figure()
    for t in [c for c in vh.columns if c != "total"]:
        fig.add_trace(go.Scatter(x=vh.index, y=vh[t], name=t, stackgroup="v", mode="lines",
                                 line=dict(width=0.5, color=colors.get(t)),
                                 hovertemplate=f"{t}: €%{{y:,.0f}}<extra></extra>"))
    fig.add_trace(go.Scatter(x=vh.index, y=[cost_eur] * len(vh), name="Cost basis", mode="lines",
                             line=dict(color=INK_2, width=1.5, dash="dash"),
                             hovertemplate="Cost: €%{y:,.0f}<extra></extra>"))
    fig = _base(fig, height=380)
    fig.update_layout(title=dict(text="Value of current positions over time (EUR)", font=dict(color=INK, size=14)))
    fig.update_yaxes(tickprefix="€")
    return fig


def indexed_lines(df: pd.DataFrame, colors: dict[str, str], title: str, height: int = 380) -> go.Figure:
    fig = go.Figure()
    for col in df.columns:
        s = df[col].dropna()
        if s.empty:
            continue
        width = 3 if col == "Your portfolio" else 2
        fig.add_trace(go.Scatter(x=s.index, y=s, name=col, mode="lines", line=dict(color=colors.get(col), width=width),
                                 hovertemplate=f"{col}: %{{y:.1f}}<extra></extra>"))
        fig.add_annotation(x=s.index[-1], y=s.iloc[-1], text=f"{s.iloc[-1] - 100:+.0f}%", showarrow=False,
                           xanchor="left", xshift=6, font=dict(color=INK_2, size=11))
    fig.add_hline(y=100, line=dict(color=AXIS, width=1))
    fig = _base(fig, height=height)
    fig.update_layout(title=dict(text=title, font=dict(color=INK, size=14)), margin=dict(r=48))
    return fig


def diverging_scores(scores: dict[str, float], title: str, height: int | None = None) -> go.Figure:
    items = [(k, v) for k, v in scores.items() if v is not None and not math.isnan(v)]
    items.sort(key=lambda kv: kv[1])
    fig = go.Figure(go.Bar(
        x=[v for _, v in items], y=[k for k, _ in items], orientation="h",
        marker=dict(color=[score_color(v) for _, v in items], line=dict(color=SURFACE, width=2)),
        text=[f"{v:+.0f}" for _, v in items], textposition="outside", textfont=dict(color=INK_2), cliponaxis=False,
        hovertemplate="%{y}: %{x:+.0f}<extra></extra>",
    ))
    fig = _base(fig, height=height or 70 + 34 * len(items), legend=False)
    fig.update_layout(hovermode="closest", title=dict(text=title, font=dict(color=INK, size=14)))
    fig.update_xaxes(range=[-118, 118], tickvals=[-100, -50, 0, 50, 100],
                     ticktext=["-100<br>bearish", "-50", "0", "+50", "+100<br>bullish"],
                     zeroline=True, zerolinecolor=AXIS)
    return fig


def gauge(value: float, title: str) -> go.Figure:
    v = 0 if value is None or math.isnan(value) else value
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=v, number=dict(font=dict(color=INK, size=34), valueformat="+.0f"),
        title=dict(text=title, font=dict(color=INK_2, size=13)),
        gauge=dict(
            axis=dict(range=[-100, 100], tickvals=[-100, -50, 0, 50, 100], tickcolor=MUTED, tickfont=dict(color=MUTED)),
            bar=dict(color=INK, thickness=0.25),
            bgcolor="rgba(0,0,0,0)", borderwidth=0,
            steps=[dict(range=[-100, -50], color="#7a2e2e"), dict(range=[-50, -15], color="#4a2a2a"),
                   dict(range=[-15, 15], color=NEUTRAL), dict(range=[15, 50], color="#1f3553"),
                   dict(range=[50, 100], color="#1c4a82")],
        ),
    ))
    fig.update_layout(height=200, margin=dict(l=45, r=45, t=40, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(color=INK_2))
    return fig


def fear_greed_history(series: pd.Series) -> go.Figure:
    fig = go.Figure(go.Scatter(x=series.index, y=series, mode="lines", name="Fear & Greed",
                               line=dict(color=BULL, width=2), hovertemplate="%{y:.0f}<extra></extra>"))
    for y, txt in ((25, "Extreme fear"), (45, "Fear"), (55, "Greed"), (75, "Extreme greed")):
        fig.add_hline(y=y, line=dict(color=GRID, width=1, dash="dot"))
    fig.add_annotation(x=series.index[0], y=12, text="Extreme fear", showarrow=False, xanchor="left", font=dict(color=MUTED))
    fig.add_annotation(x=series.index[0], y=88, text="Extreme greed", showarrow=False, xanchor="left", font=dict(color=MUTED))
    fig = _base(fig, height=280, legend=False)
    fig.update_layout(title=dict(text="CNN Fear & Greed, last 12 months", font=dict(color=INK, size=14)))
    fig.update_yaxes(range=[0, 100])
    return fig


def price_chart(ohlc: pd.DataFrame, ticker: str, color: str, avg_cost: float | None = None,
                scenarios: dict | None = None, levels: dict | None = None, currency: str = "") -> go.Figure:
    from .indicators import rsi, sma

    close = ohlc["Close"]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.04)
    fig.add_trace(go.Scatter(x=close.index, y=close, name=ticker, mode="lines", line=dict(color=color, width=2),
                             hovertemplate="%{y:.2f}<extra>" + ticker + "</extra>"), row=1, col=1)
    s50, s200 = sma(close, 50), sma(close, 200)
    fig.add_trace(go.Scatter(x=close.index, y=s50, name="50-day avg", mode="lines",
                             line=dict(color=INK_2, width=1.2, dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=close.index, y=s200, name="200-day avg", mode="lines",
                             line=dict(color=MUTED, width=1.2, dash="dash")), row=1, col=1)
    if avg_cost:
        fig.add_hline(y=avg_cost, line=dict(color=WARNING, width=1.2, dash="dash"), row=1, col=1,
                      annotation_text=f"Your cost {avg_cost:,.2f}", annotation_position="top left",
                      annotation_font_color=WARNING)
    for lv in (levels or {}).get("support", []):
        fig.add_hline(y=lv, line=dict(color=GOOD, width=0.8, dash="dot"), row=1, col=1, opacity=0.6)
    for lv in (levels or {}).get("resistance", []):
        fig.add_hline(y=lv, line=dict(color=CRITICAL, width=0.8, dash="dot"), row=1, col=1, opacity=0.6)
    r = rsi(close)
    fig.add_trace(go.Scatter(x=close.index, y=r, name="RSI (14)", mode="lines", line=dict(color=INK_2, width=1.2),
                             showlegend=False, hovertemplate="RSI %{y:.0f}<extra></extra>"), row=2, col=1)
    for y in (30, 70):
        fig.add_hline(y=y, line=dict(color=GRID, width=1, dash="dot"), row=2, col=1)
    fig = _base(fig, height=460)
    fig.update_yaxes(title_text=currency, row=1, col=1, title_font=dict(color=MUTED))
    fig.update_yaxes(title_text="RSI", range=[0, 100], tickvals=[30, 70], row=2, col=1, title_font=dict(color=MUTED))
    return fig


def scenario_dots(tab: pd.DataFrame, cost_move: dict[str, float], colors: dict[str, str]) -> go.Figure:
    """Upside to bear/base/bull per holding on one % axis, with the break-even move marked."""
    fig = go.Figure()
    tickers = list(dict.fromkeys(tab["ticker"]))
    for t in tickers:
        sub = tab[tab["ticker"] == t].set_index("case")
        lo, hi = sub["upside"].min() * 100, sub["upside"].max() * 100
        fig.add_trace(go.Scatter(x=[lo, hi], y=[t, t], mode="lines", line=dict(color=colors[t], width=6),
                                 opacity=0.35, showlegend=False, hoverinfo="skip"))
        for case, sym in (("bear", "triangle-left"), ("base", "circle"), ("bull", "triangle-right")):
            if case in sub.index:
                u = sub.loc[case, "upside"] * 100
                fig.add_trace(go.Scatter(
                    x=[u], y=[t], mode="markers+text", marker=dict(symbol=sym, size=14, color=colors[t],
                                                                  line=dict(color=SURFACE, width=2)),
                    text=[f"{case} {u:+.0f}%"], textposition="top center", textfont=dict(color=INK_2, size=10),
                    showlegend=False, hovertemplate=f"{t} {case}: target {sub.loc[case, 'target']:.2f} ({u:+.0f}%)<extra></extra>"))
        be = cost_move.get(t)
        if be is not None and not math.isnan(be):
            fig.add_trace(go.Scatter(x=[be * 100], y=[t], mode="markers", marker=dict(symbol="line-ns-open", size=22,
                                     color=WARNING, line=dict(width=2)), showlegend=False,
                                     hovertemplate=f"{t} back to your cost: {be * 100:+.0f}%<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=AXIS, width=1))
    fig = _base(fig, height=90 + 70 * len(tickers), legend=False)
    fig.update_layout(hovermode="closest",
                      title=dict(text="Upside to 12-month scenarios (yellow tick = back to your cost)", font=dict(color=INK, size=14)))
    fig.update_xaxes(ticksuffix="%")
    fig.update_yaxes(autorange="reversed")
    return fig


def cone_chart(close: pd.Series, ranges: pd.DataFrame, color: str, targets: dict[str, float] | None = None,
               avg_cost: float | None = None) -> go.Figure:
    """Last 6 months of price plus 1-sigma / 2-sigma volatility cone and scenario targets."""
    hist = close.dropna().tail(126)
    last_date, last = hist.index[-1], float(hist.iloc[-1])
    dates = [last_date] + [last_date + pd.DateOffset(months=int(m)) for m in ranges["months"]]
    fig = go.Figure()
    for lo, hi, name, alpha in (("low_2s", "high_2s", "~95% range", 0.12), ("low_1s", "high_1s", "~68% range", 0.25)):
        upper = [last] + list(ranges[hi])
        lower = [last] + list(ranges[lo])
        fig.add_trace(go.Scatter(x=dates + dates[::-1], y=upper + lower[::-1], fill="toself", mode="lines",
                                 line=dict(width=0), fillcolor=_rgba(color, alpha), name=name, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=dates, y=upper, mode="lines", line=dict(width=0), showlegend=False,
                                 hovertemplate=f"{name} high: %{{y:.2f}}<extra></extra>"))
        fig.add_trace(go.Scatter(x=dates, y=lower, mode="lines", line=dict(width=0), showlegend=False,
                                 hovertemplate=f"{name} low: %{{y:.2f}}<extra></extra>"))
    fig.add_trace(go.Scatter(x=hist.index, y=hist, mode="lines", name="Price", line=dict(color=color, width=2),
                             hovertemplate="%{y:.2f}<extra>Price</extra>"))
    end = dates[-1]
    for case, sym in (("bear", "triangle-down"), ("base", "circle"), ("bull", "triangle-up")):
        if targets and case in targets:
            fig.add_trace(go.Scatter(x=[end], y=[targets[case]], mode="markers+text", name=f"{case} target",
                                     marker=dict(symbol=sym, size=12, color=INK, line=dict(color=SURFACE, width=2)),
                                     text=[f" {case} {targets[case]:.2f}"], textposition="middle right",
                                     textfont=dict(color=INK_2), showlegend=False,
                                     hovertemplate=f"{case} target: %{{y:.2f}}<extra></extra>"))
    if avg_cost:
        fig.add_hline(y=avg_cost, line=dict(color=WARNING, width=1.2, dash="dash"),
                      annotation_text=f"Your cost {avg_cost:,.2f}", annotation_position="top left",
                      annotation_font_color=WARNING)
    fig = _base(fig, height=380)
    top = max(float(ranges["high_1s"].max()), float(hist.max()), *(targets or {}).values(), avg_cost or 0) * 1.1
    fig.update_layout(margin=dict(r=120), hovermode="closest")
    fig.update_yaxes(range=[0, top])
    return fig


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"
