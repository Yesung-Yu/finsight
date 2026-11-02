"""외부 요청·모델 없이 돌아가는 단위 테스트. 실행: python -m pytest"""
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db, market, service, ui  # noqa: E402
from src.crawler import _clean, _clean_body, candidates, dedupe, is_similar  # noqa: E402
from src.summarizer import split_lines  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "test.db")
    db.save_stocks(c, market.DEMO_STOCKS)
    return c


def sample_prices():
    idx = pd.date_range("2026-10-01", periods=5, freq="B")
    return pd.DataFrame({"open": [100, 101, 102, 103, 104], "high": [110, 111, 112, 113, 120],
                         "low": [90, 91, 92, 93, 94], "close": [100, 105, 103, 108, 104],
                         "volume": [1000, 2000, 3000, 4000, 5000]}, index=idx)


def test_resolve_by_name_and_code(conn):
    assert market.resolve(conn, "삼성전자")["code"] == "005930"
    assert market.resolve(conn, " 005930 ")["name"] == "삼성전자"
    assert market.resolve(conn, "naver")["code"] == "035420"


def test_resolve_unknown(conn):
    assert market.resolve(conn, "없는종목") is None
    assert market.resolve(conn, "") is None


def test_prices_round_trip(conn):
    db.save_prices(conn, "005930", sample_prices())
    loaded = db.load_prices(conn, "005930")
    assert list(loaded["close"]) == [100, 105, 103, 108, 104]
    assert loaded["close"].dtype.kind == "f"


def test_quote_change_down():
    q = market.quote(sample_prices())
    assert q["close"] == 104 and q["change"] == -4
    assert q["change_pct"] == pytest.approx(-3.7037, rel=1e-3)
    assert ui.color_of(q["change"]) == ui.DOWN


def test_news_dedup_by_url(conn):
    item = {"title": "t", "url": "https://a.com/1", "press": "a", "published_at": "2026-10-19 10:00:00", "body": "b"}
    assert db.save_news(conn, "005930", item) is not None
    assert db.save_news(conn, "005930", item) is None
    assert len(db.load_news(conn, "005930")) == 1


def test_sentiment_counts_match_news(conn):
    for i, s in enumerate(["호재", "악재", "호재", "중립", "호재"]):
        nid = db.save_news(conn, "005930", {"title": f"t{i}", "url": f"https://a.com/{i}",
                                            "published_at": f"2026-10-19 1{i}:00:00", "body": "b"})
        db.save_analysis(conn, nid, "요약", s, 90.0)
    db.save_prices(conn, "005930", sample_prices())
    db.set_meta(conn, "updated:005930", db.now_str())
    view = service.get_view(conn, db.get_stock(conn, "005930"))  # 오늘 갱신됨 → 외부 요청 없이 캐시 사용
    assert view.from_cache
    assert view.sentiment_counts == {"호재": 3, "중립": 1, "악재": 1}
    assert sum(view.sentiment_counts.values()) == len(view.news)


def test_cached_stock_list(conn):
    db.set_meta(conn, "updated:000660", "2026-10-18 09:00:00")
    assert [s["name"] for s in db.cached_stock_list(conn)] == ["SK하이닉스"]


def test_format_helpers():
    assert ui.big_won(1_234_5000_0000_0000) == "1,234조 5,000억원"
    assert ui.big_won(None) == "-"
    assert ui.times(12.345) == "12.35배"


def test_candidates_prefer_title_and_alias():
    items = [
        {"title": "코스피 마감", "description": "삼성전자 등 반도체주 상승", "url": "1"},
        {"title": "용인 교통망 확충", "description": "도로 공동 추진", "url": "2"},
        {"title": "삼성전자, 실적 발표", "description": "", "url": "3"},
        {"title": "네이버, AI 투자", "description": "", "url": "4"},
    ]
    assert [it["url"] for it in candidates("삼성전자", items)] == ["3", "1"]
    assert [it["url"] for it in candidates("NAVER", items)] == ["4"]


def test_candidates_exclude_longer_names():
    items = [{"title": t, "description": "", "url": str(i)} for i, t in enumerate(
        ["카카오게임즈 신작", "카카오맵 단풍 지도", "카카오, 3분기 실적", "카카오는 AI에 투자", "‘카카오’ 주가 반등", "AI 키우는 카카오"])]
    assert [it["url"] for it in candidates("카카오", items)] == ["2", "3", "4", "5"]


def test_similar_titles_merged():
    # 실제 수집된 제목 (2026-10-19)
    assert is_similar("[비즈투데이] 삼성전자, 99개 기업에 기술 126건 무상 나눔", "삼성전자, 중기에 126건 기술나눔", "삼성전자")
    assert is_similar("에코프로비엠 유증 청약률 103.25%…삼성SDI 웃돌아", "에코프로비엠, 유상증자 청약률 103.25%", "에코프로비엠")
    assert not is_similar("삼성전자 DX 노조 \"이재용 회장, 직접 대화해달라\"", "삼성전자, 중기에 126건 기술나눔", "삼성전자")
    assert not is_similar("장 초반 3% 급락 딛고 웃었다…코스피 5768선 ‘반전 마감’",
                          "이틀 연속 상승세, 코스피 코스닥 활짝 웃었다 - 이차전지 관련주 강세", "삼성전자")
    items = [{"title": t} for t in ["삼성전자, 중기에 126건 기술나눔", "삼성전자 특허 126건 ‘통 큰 나눔’…중소기업 99곳에 무료 이전",
                                    "삼성전자 DX 노조 \"이재용 회장, 직접 대화해달라\""]]
    assert [it["title"][:8] for it in dedupe(items, "삼성전자")] == ["삼성전자, 중기", "삼성전자 DX "]


def test_short_titles_need_near_match():
    assert not is_similar("삼성전자 주가", "삼성전자 주가 급락 우려", "삼성전자")


def test_text_cleaning():
    assert _clean("<b>삼성전자</b> &quot;실적&quot;") == '삼성전자 "실적"'
    assert "무단" not in _clean_body("본문입니다.\n홍길동 기자 hong@a.com\n무단전재 및 재배포 금지")
    assert split_lines("삼성전자가 3분기 3분기 실적을 냈다. 삼성전자가 3분기 실적을 냈다.") == ["삼성전자가 3분기 실적을 냈다."]


def test_market_loads_when_pykrx_import_fails(monkeypatch):
    """오프라인에서 pykrx 로그인이 실패해도 앱은 캐시로 떠야 한다."""
    with monkeypatch.context() as m:
        m.setitem(sys.modules, "pykrx", None)
        importlib.reload(market)
        assert market.krx is None
        with pytest.raises(RuntimeError):
            market.fetch_prices("005930")
    importlib.reload(market)
    assert market.krx is not None
