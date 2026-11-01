"""주식 뉴스 요약 · 투자 보조 — Streamlit 메인 화면.

실행: streamlit run app.py
"""
import os
import threading

import streamlit as st

from src import db, market, service, ui

KIOSK = os.environ.get("FINSIGHT_KIOSK") == "1"  # 전시 모드: 여러 명이 접속하므로 새로고침 버튼을 숨긴다

st.set_page_config(page_title="주식 뉴스 요약 · 투자 보조", page_icon="📈", layout="wide")
ui.inject_css()


@st.cache_resource
def get_conn():
    conn = db.connect()
    market.ensure_stock_list(conn)
    return conn


@st.cache_resource(show_spinner="요약·감성 분석 모델을 불러오는 중입니다... (처음 한 번만)")
def get_models():
    return service.load_models()


@st.cache_resource
def get_collect_lock():
    """새 종목 수집·분석은 한 번에 하나씩만 돌린다. 여러 관람객이 동시에 검색해도 PC가 멈추지 않게 한다."""
    return threading.Lock()


conn = get_conn()
summarizer, analyzer = get_models()


def pick(name: str) -> None:
    st.session_state.query = name


def finish() -> None:
    """사이드바의 저장된 종목 목록과 하단 안내를 그리고 끝낸다. 수집 결과가 반영되도록 마지막에 그린다."""
    with cached_box:
        st.subheader("저장된 종목")
        cached = db.cached_stock_list(conn)
        if not cached:
            st.caption("아직 저장된 종목이 없습니다.")
        for s in cached:
            st.button(f"{s['name']} ({s['code']})", key=f"cached-{s['code']}", on_click=pick, args=(s["name"],),
                      width="stretch")
            st.caption(f"마지막 갱신 {s['updated_at'][:16]}")
    ui.footer()
    st.stop()


# ---------- 사이드바 (FR-9) ----------
with st.sidebar:
    refresh = False
    if not KIOSK:
        st.subheader("관리")
        refresh = st.button("데이터 새로고침", width="stretch", type="primary",
                            help="선택한 종목의 시세와 뉴스를 다시 수집합니다.")
    if summarizer is None or analyzer is None:
        st.warning("AI 모델을 불러오지 못해 새 뉴스는 요약·판정 없이 표시됩니다.")
    cached_box = st.container()

# ---------- 상단 검색 (FR-1) ----------
top_left, top_right = st.columns([11, 10], gap="large")  # 아래 2단과 같은 비율로 맞춘다
with top_left:
    query = st.text_input("종목 검색", key="query", placeholder="종목명 또는 종목코드 (예: 삼성전자, 005930)",
                          label_visibility="collapsed")
top_right.markdown('<div class="fs-header">주식 뉴스 요약 · 투자 보조</div>', unsafe_allow_html=True)

if not query.strip():
    st.markdown("#### 종목을 검색해 보세요")
    st.write("종목 하나만 검색하면 시세·차트·투자 지표와 최신 뉴스 요약, 호재·악재 판정을 한 화면에서 볼 수 있습니다.")
    cols = st.columns(5)
    for col, (code, name, _) in zip(cols * 2, market.DEMO_STOCKS):
        col.button(name, key=f"demo-{code}", on_click=pick, args=(name,), width="stretch")
    finish()

stock = market.resolve(conn, query)
if stock is None:
    st.warning(f"'{query}' 종목을 찾을 수 없습니다. 종목명이나 6자리 종목코드를 확인해 주세요.")
    similar = db.search_stock_names(conn, query.strip(), limit=5) if not query.strip().isdigit() else []
    if similar:
        st.write("혹시 이 종목을 찾으시나요?")
        for col, s in zip(st.columns(len(similar)), similar):
            col.button(s["name"], key=f"similar-{s['code']}", on_click=pick, args=(s["name"],))
    finish()

spinner = ("처음 검색하는 종목입니다. 시세와 뉴스를 수집하고 분석하는 중입니다... (최대 1분 정도 걸립니다)"
           if refresh or not (service.is_fresh(conn, stock["code"]) or service.recently_failed(conn, stock["code"]))
           else None)
if spinner:
    lock = get_collect_lock()
    if lock.locked():
        st.caption("다른 종목을 분석하고 있어서 순서를 기다리는 중입니다.")
    with st.spinner(spinner):
        with lock:  # 기다리는 동안 다른 사람이 같은 종목을 끝냈다면 get_view가 캐시를 그대로 쓴다
            view = service.get_view(conn, stock, summarizer, analyzer, force_refresh=refresh)
else:
    view = service.get_view(conn, stock, summarizer, analyzer)

if view.prices.empty and not view.news:
    st.error("데이터를 가져오지 못했고 저장된 데이터도 없습니다. 인터넷 연결을 확인해 주세요."
             if KIOSK else
             "데이터를 가져오지 못했고 저장된 데이터도 없습니다. 인터넷 연결을 확인한 뒤 '데이터 새로고침'을 눌러 주세요.")
    for e in view.errors:
        st.caption(e)
    finish()

# ---------- 수집 오류 안내 ----------
for e in view.errors:
    st.caption(f"⚠️ {e}")

# ---------- 2단 화면 ----------
left, right = st.columns([11, 10], gap="large")

with left:
    ui.stock_header(view.stock, view.quote)
    head, sel = st.columns([1, 1])
    head.markdown('<div class="fs-section">주가 추이</div>', unsafe_allow_html=True)
    with sel:
        period = st.segmented_control("기간", list(ui.PERIODS), default="1개월", key="period",
                                      label_visibility="collapsed") or "1개월"
    ui.price_chart(view.prices, period)
    st.markdown('<div class="fs-section">투자 지표</div>', unsafe_allow_html=True)
    ui.indicator_cards(view.fundamentals, view.quote)

with right:
    st.markdown('<div class="fs-section">오늘의 호재·악재</div>', unsafe_allow_html=True)
    ui.sentiment_bar(view.sentiment_counts)
    st.markdown(f'<div class="fs-section">관련 뉴스 {len(view.news)}건</div>', unsafe_allow_html=True)
    if not view.news:
        st.caption("수집된 뉴스가 없습니다.")
    for n in view.news:
        ui.news_card(n)

finish()
