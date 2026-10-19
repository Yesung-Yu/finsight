"""시세·뉴스·요약·판정을 묶어 한 화면에 필요한 데이터를 만든다 (FR-8 캐시 포함)."""
from __future__ import annotations

import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd
import requests

from src import crawler, db, market

NEWS_LIMIT = 5
RETRY_AFTER = timedelta(minutes=10)  # 수집에 실패한 종목은 이 시간 동안 다시 시도하지 않는다
OFFLINE_MESSAGE = "인터넷에 연결되어 있지 않아 저장된 데이터를 보여 줍니다."


@dataclass
class StockView:
    stock: dict
    prices: pd.DataFrame
    quote: dict | None
    fundamentals: dict | None
    news: list[dict]
    from_cache: bool  # 이번 요청에서 새로 받지 않고 저장된 데이터를 보여주는지
    updated_at: str | None
    errors: list[str] = field(default_factory=list)

    @property
    def sentiment_counts(self) -> dict[str, int]:
        counts = {"호재": 0, "중립": 0, "악재": 0}
        for n in self.news:
            if n.get("sentiment") in counts:
                counts[n["sentiment"]] += 1
        return counts


def load_models():
    """(요약 모델, 감성 모델). 저장된 모델 파일을 먼저 쓰고, 없으면 내려받는다. 실패한 모델은 None."""
    from src.sentiment import SentimentAnalyzer
    from src.summarizer import Summarizer

    loaded = []
    for cls in (Summarizer, SentimentAnalyzer):
        try:
            loaded.append(cls(local_files_only=True))
        except Exception:
            try:
                loaded.append(cls())
            except Exception:
                loaded.append(None)
    return tuple(loaded)


def analyze_pending(conn, code: str, summarizer, analyzer, limit: int = NEWS_LIMIT) -> None:
    """아직 요약·판정하지 않은 기사를 처리한다. 같은 기사는 다시 처리하지 않는다 (FR-6, FR-7)."""
    if summarizer is None or analyzer is None:
        return
    for n in db.load_news(conn, code, limit):
        if n["summary"] is not None:
            continue
        summary = summarizer.summarize(n["body"] or n["title"])
        sentiment, confidence = analyzer.predict(n["title"], summary)
        db.save_analysis(conn, n["id"], summary, sentiment, confidence)


def is_online(timeout: float = 1.0) -> bool:
    """뉴스 API 서버에 연결되는지 빠르게 확인한다."""
    try:
        socket.create_connection((crawler.API["hub"][0].split("/")[2], 443), timeout=timeout).close()
        return True
    except OSError:
        return False


def _friendly(what: str, e: Exception) -> str:
    if isinstance(e, requests.RequestException):
        return f"{what} 서버에 연결하지 못했습니다."
    return f"{what} 수집 실패: {e}"


def update_stock(conn, stock, summarizer=None, analyzer=None, news_limit: int = NEWS_LIMIT) -> list[str]:
    """시세·뉴스를 새로 수집하고 분석한다. 실패한 항목의 오류 메시지 목록을 돌려준다."""
    code, name = stock["code"], stock["name"]
    errors = []
    try:
        market.refresh(conn, code)
    except Exception as e:
        errors.append(_friendly("시세", e))
    try:
        for item in crawler.collect(name, limit=news_limit, skip_url=lambda url: db.news_exists(conn, url)):
            if not item["cached"]:
                db.save_news(conn, code, item)
    except Exception as e:
        errors.append(_friendly("뉴스", e))
    try:
        analyze_pending(conn, code, summarizer, analyzer, news_limit)
    except Exception as e:
        errors.append(f"뉴스 분석 실패: {e}")
    if len(errors) < 2:  # 시세·뉴스 중 하나라도 받았으면 갱신 시각 기록
        db.set_meta(conn, f"updated:{code}", db.now_str())
    else:
        db.set_meta(conn, f"failed:{code}", db.now_str())
    return errors


def recently_failed(conn, code: str) -> bool:
    failed = db.get_meta(conn, f"failed:{code}")
    return bool(failed) and datetime.now() - datetime.fromisoformat(failed) < RETRY_AFTER


def is_fresh(conn, code: str) -> bool:
    """오늘 이미 갱신했으면 True."""
    updated = db.get_meta(conn, f"updated:{code}")
    return bool(updated) and updated[:10] == datetime.now().strftime("%Y-%m-%d")


def get_view(conn, stock, summarizer=None, analyzer=None, force_refresh: bool = False) -> StockView:
    code = stock["code"]
    errors: list[str] = []
    fetched = False
    needs_update = force_refresh or not (is_fresh(conn, code) or recently_failed(conn, code))
    if needs_update and not is_online():
        errors = [OFFLINE_MESSAGE]
    elif needs_update:
        errors = update_stock(conn, stock, summarizer, analyzer)
        fetched = len(errors) < 2
    else:
        try:  # 이전에 모델 없이 수집한 기사가 있으면 지금 분석
            analyze_pending(conn, code, summarizer, analyzer)
        except Exception as e:
            errors.append(f"뉴스 분석 실패: {e}")
    prices = db.load_prices(conn, code)
    return StockView(
        stock=dict(db.get_stock(conn, code)),
        prices=prices,
        quote=market.quote(prices),
        fundamentals=db.load_latest_fundamentals(conn, code),
        news=db.load_news(conn, code, NEWS_LIMIT),
        from_cache=not fetched,
        updated_at=db.get_meta(conn, f"updated:{code}"),
        errors=errors,
    )
