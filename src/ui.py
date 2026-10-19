"""화면 구성 요소 (요구사항 4장)."""
from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

UP, DOWN, FLAT = "#d6293e", "#1e5bd6", "#8a8f98"  # 국내 증시 관례: 상승 빨강, 하락 파랑
BADGE = {"호재": UP, "악재": DOWN, "중립": FLAT}
PERIODS = {"1주": 7, "1개월": 30, "3개월": 91}
MARKET_NAMES = {"KOSPI": "코스피", "KOSDAQ": "코스닥", "KONEX": "코넥스"}

TOOLTIPS = {
    "시가총액": "회사 전체의 가격입니다. 주가 × 발행 주식 수로 계산합니다.",
    "거래량": "가장 최근 거래일에 사고팔린 주식 수입니다. 많을수록 관심이 많다는 뜻입니다.",
    "PER": "주가수익비율. 주가가 1주당 순이익의 몇 배인지 나타냅니다. 같은 업종끼리 비교했을 때 낮으면 이익에 비해 싸다고 봅니다.",
    "PBR": "주가순자산비율. 주가가 1주당 순자산(자본)의 몇 배인지 나타냅니다. 1보다 낮으면 장부상 자산보다 싸게 거래된다는 뜻입니다.",
    "52주 최고": "최근 1년(52주) 동안 가장 높았던 가격입니다.",
    "52주 최저": "최근 1년(52주) 동안 가장 낮았던 가격입니다.",
}

CSS = """
<style>
.block-container {padding-top: 2.2rem; padding-bottom: 1rem;}
.fs-header {text-align: right; color: #6b7280; font-size: 0.95rem; padding-top: 0.55rem;}
.fs-name {font-size: 1.75rem; font-weight: 700; margin: 0;}
.fs-sub {color: #6b7280; font-size: 0.95rem; margin-left: 0.4rem;}
.fs-price {font-size: 2.1rem; font-weight: 700; line-height: 1.2;}
.fs-change {font-size: 1.05rem; font-weight: 600; margin-left: 0.6rem;}
.fs-section {font-weight: 700; font-size: 1.1rem; margin: 0.6rem 0 0.3rem;}
.fs-bar {display: flex; height: 26px; border-radius: 6px; overflow: hidden; margin: 0.3rem 0 0.4rem;}
.fs-bar div {display: flex; align-items: center; justify-content: center; color: #fff;
             font-size: 0.8rem; font-weight: 600; white-space: nowrap; overflow: hidden;}
.fs-legend {display: flex; gap: 1rem; font-size: 0.9rem; color: #4b5563;}
.fs-dot {display: inline-block; width: 0.7rem; height: 0.7rem; border-radius: 50%; margin-right: 0.3rem;}
.fs-badge {display: inline-block; padding: 0.1rem 0.55rem; border-radius: 999px; color: #fff;
           font-size: 0.8rem; font-weight: 700; margin-right: 0.45rem; vertical-align: 2px;}
.fs-title a {font-weight: 650; font-size: 1.02rem; color: inherit; text-decoration: none;}
.fs-title a:hover {text-decoration: underline;}
.fs-meta {color: #6b7280; font-size: 0.82rem; margin: 0.15rem 0 0.35rem;}
.fs-summary {margin: 0 0 0.3rem 1.1rem; padding: 0; font-size: 0.93rem;}
.fs-summary li {margin-bottom: 0.15rem;}
.fs-judge {color: #6b7280; font-size: 0.82rem;}
.fs-footer {color: #9ca3af; font-size: 0.8rem; text-align: center; margin-top: 1.5rem;
            border-top: 1px solid rgba(128,128,128,0.2); padding-top: 0.7rem;}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


# ---------- 숫자 표시 ----------
def won(v) -> str:
    return "-" if v is None else f"{v:,.0f}원"


def big_won(v) -> str:
    """시가총액: 조/억 단위"""
    if v is None:
        return "-"
    jo, eok = divmod(round(v / 1e8), 10000)
    if jo:
        return f"{jo:,}조 {eok:,}억원" if eok else f"{jo:,}조원"
    return f"{eok:,}억원"


def times(v) -> str:
    return "-" if v is None else f"{v:,.2f}배"


def shares(v) -> str:
    return "-" if v is None else f"{v:,.0f}주"


def color_of(change: float) -> str:
    return UP if change > 0 else DOWN if change < 0 else FLAT


# ---------- 왼쪽: 시세 ----------
def stock_header(stock: dict, quote: dict | None) -> None:
    market = MARKET_NAMES.get(stock.get("market") or "", "-")
    st.markdown(
        f'<p class="fs-name">{html.escape(stock["name"])}'
        f'<span class="fs-sub">{stock["code"]} · {market}</span></p>',
        unsafe_allow_html=True,
    )
    if quote is None:
        st.markdown('<div class="fs-price">-</div>', unsafe_allow_html=True)
        return
    c = quote["change"]
    arrow = "▲" if c > 0 else "▼" if c < 0 else "-"
    st.markdown(
        f'<div class="fs-price" style="color:{color_of(c)}">{quote["close"]:,.0f}원'
        f'<span class="fs-change">{arrow} {abs(c):,.0f} ({quote["change_pct"]:+.2f}%)</span></div>'
        f'<div class="fs-meta">{quote["date"]} 종가 기준 · 전일 대비</div>',
        unsafe_allow_html=True,
    )


def price_chart(prices: pd.DataFrame, period: str) -> None:
    if prices.empty:
        st.info("시세 데이터가 없습니다.")
        return
    start = prices.index[-1] - pd.Timedelta(days=PERIODS[period])
    df = prices[prices.index > start]
    color = color_of(df["close"].iloc[-1] - df["close"].iloc[0])
    fig = go.Figure(go.Scatter(
        x=df.index, y=df["close"], mode="lines+markers" if len(df) <= 10 else "lines",
        line=dict(color=color, width=2.4), marker=dict(size=6),
        hovertemplate="%{x|%Y-%m-%d}<br>종가 %{y:,.0f}원<extra></extra>",
    ))
    fig.update_layout(
        height=300, margin=dict(l=8, r=8, t=8, b=8), showlegend=False,
        xaxis=dict(tickformat="%m/%d", showgrid=False),
        yaxis=dict(tickformat=",", gridcolor="rgba(128,128,128,0.18)"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def indicator_cards(fund: dict | None, quote: dict | None) -> None:
    fund = fund or {}
    values = {
        "시가총액": big_won(fund.get("market_cap")),
        "거래량": shares(quote["volume"] if quote else None),
        "PER": times(fund.get("per")),
        "PBR": times(fund.get("pbr")),
        "52주 최고": won(fund.get("high_52w")),
        "52주 최저": won(fund.get("low_52w")),
    }
    items = list(values.items())
    for row in (items[:3], items[3:]):
        for col, (label, value) in zip(st.columns(3), row):
            col.metric(label, value, help=TOOLTIPS[label], border=True)


# ---------- 오른쪽: 뉴스 ----------
def sentiment_bar(counts: dict[str, int]) -> None:
    total = sum(counts.values())
    if total == 0:
        st.caption("판정된 뉴스가 없습니다.")
        return
    segs = "".join(
        f'<div style="width:{n / total * 100:.1f}%;background:{BADGE[k]}">{k} {n}</div>'
        for k, n in counts.items() if n
    )
    legend = "".join(
        f'<span><span class="fs-dot" style="background:{BADGE[k]}"></span>{k} {n}건 ({n / total:.0%})</span>'
        for k, n in counts.items()
    )
    st.markdown(f'<div class="fs-bar">{segs}</div><div class="fs-legend">{legend}</div>',
                unsafe_allow_html=True)


def _short_time(ts: str | None) -> str:
    return ts[5:16] if ts else ""


def news_card(n: dict) -> None:
    sentiment = n.get("sentiment")
    badge = (f'<span class="fs-badge" style="background:{BADGE[sentiment]}">{sentiment}</span>'
             if sentiment else '<span class="fs-badge" style="background:#c4c7cc">분석 전</span>')
    lines = [l for l in (n.get("summary") or "").split("\n") if l.strip()]
    summary = ("<ul class='fs-summary'>" + "".join(f"<li>{html.escape(l)}</li>" for l in lines) + "</ul>"
               if lines else "")
    judge = (f'<div class="fs-judge">KR-FinBERT 판정 · 신뢰도 {n["confidence"]:.1f}%</div>'
             if sentiment else "")
    meta = " · ".join(x for x in (n.get("press"), _short_time(n.get("published_at"))) if x)
    with st.container(border=True):
        st.markdown(
            f'<div class="fs-title">{badge}<a href="{html.escape(n["url"])}" target="_blank">'
            f'{html.escape(n["title"])}</a></div>'
            f'<div class="fs-meta">{html.escape(meta)}</div>{summary}{judge}',
            unsafe_allow_html=True,
        )


def footer() -> None:
    st.markdown(
        '<div class="fs-footer">이 사이트는 정보 제공을 목적으로 하며 투자 추천이나 매수·매도 신호를 제공하지 않습니다. '
        "뉴스 요약과 호재·악재 판정은 AI 모델의 결과로 틀릴 수 있으며, 투자 판단의 책임은 이용자 본인에게 있습니다.</div>",
        unsafe_allow_html=True,
    )
