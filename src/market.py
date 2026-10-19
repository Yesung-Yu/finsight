"""pykrx 시세·지표 수집 (FR-1~4).

pykrx 1.2.x 부터 종목 목록·PER/PBR·시가총액은 KRX 정보데이터시스템(data.krx.co.kr) 로그인이 필요하다.
.env 에 KRX_ID / KRX_PW 를 넣으면 자동 로그인되고, 없으면 해당 값은 None("-" 표시)이 된다.
일별 시세(OHLCV)는 로그인 없이 받을 수 있으므로 거래량·52주 최고/최저는 시세로 계산한다.
"""
from __future__ import annotations

import contextlib
import io
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # pykrx가 import 시점에 KRX_ID/KRX_PW를 읽으므로 먼저 불러온다

with contextlib.redirect_stdout(io.StringIO()):  # pykrx의 로그인 안내 출력 숨김
    from pykrx import stock as krx

from src import db

# KRX 로그인이 없을 때도 검색되도록 내장한 시연 종목
DEMO_STOCKS = [
    ("005930", "삼성전자", "KOSPI"),
    ("000660", "SK하이닉스", "KOSPI"),
    ("373220", "LG에너지솔루션", "KOSPI"),
    ("005380", "현대차", "KOSPI"),
    ("000270", "기아", "KOSPI"),
    ("035420", "NAVER", "KOSPI"),
    ("035720", "카카오", "KOSPI"),
    ("068270", "셀트리온", "KOSPI"),
    ("247540", "에코프로비엠", "KOSDAQ"),
    ("196170", "알테오젠", "KOSDAQ"),
]

PRICE_COLUMNS = {"시가": "open", "고가": "high", "저가": "low", "종가": "close", "거래량": "volume"}


def _quiet(func, *args, **kwargs):
    """pykrx 내부 print 를 숨기고 호출한다."""
    with contextlib.redirect_stdout(io.StringIO()):
        return func(*args, **kwargs)


def _ymd(d: datetime) -> str:
    return d.strftime("%Y%m%d")


def _num(value) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(v) or v == 0 else v


# ---------- FR-1 종목 목록 ----------
def ensure_stock_list(conn) -> int:
    """종목 목록을 DB에 채운다. KRX 로그인이 안 되면 시연 종목만 넣는다."""
    db.save_stocks(conn, DEMO_STOCKS)
    if db.count_stocks(conn) > len(DEMO_STOCKS):
        return db.count_stocks(conn)
    rows = []
    try:
        for market in ("KOSPI", "KOSDAQ"):
            for code in _quiet(krx.get_market_ticker_list, market=market):
                rows.append((code, _quiet(krx.get_market_ticker_name, code), market))
    except Exception:
        rows = []
    if rows:
        db.save_stocks(conn, rows)
    return db.count_stocks(conn)


def resolve(conn, query: str):
    """종목명 또는 6자리 종목코드 → stocks 행. 없으면 None."""
    q = query.strip()
    if not q:
        return None
    if q.isdigit() and len(q) == 6:
        row = db.get_stock(conn, q)
        if row:
            return row
        try:  # 목록에 없는 코드는 pykrx에 이름을 물어본다
            name = _quiet(krx.get_market_ticker_name, q)
        except Exception:
            name = None
        if isinstance(name, str) and name:
            db.save_stocks(conn, [(q, name, None)])
            return db.get_stock(conn, q)
        return None
    return db.find_stock_by_name(conn, q)


# ---------- FR-2~4 시세·지표 ----------
def fetch_prices(code: str, days: int = 400) -> pd.DataFrame:
    """최근 days일 일별 시세. 실패하면 예외."""
    end = datetime.now()
    df = _quiet(krx.get_market_ohlcv, _ymd(end - timedelta(days=days)), _ymd(end), code)
    if df is None or df.empty:
        raise RuntimeError(f"{code} 시세를 가져오지 못했습니다.")
    df = df.rename(columns=PRICE_COLUMNS)[list(PRICE_COLUMNS.values())]
    df = df[df["close"] > 0]  # 거래정지일 제거
    df.index = pd.to_datetime(df.index)
    return df


def fetch_fundamentals(code: str, prices: pd.DataFrame) -> dict:
    """투자 지표. 받지 못한 값은 None."""
    last_date = prices.index[-1]
    year_ago = last_date - pd.Timedelta(days=365)
    recent = prices[prices.index > year_ago]
    result = {
        "market_cap": None,
        "per": None,
        "pbr": None,
        "high_52w": _num(recent["high"].max()),
        "low_52w": _num(recent["low"].min()),
    }
    d = _ymd(last_date)
    try:
        cap = _quiet(krx.get_market_cap, d, d, code)
        if cap is not None and not cap.empty:
            result["market_cap"] = _num(cap["시가총액"].iloc[-1])
    except Exception:
        pass
    try:
        fund = _quiet(krx.get_market_fundamental, d, d, code)
        if fund is not None and not fund.empty:
            result["per"] = _num(fund["PER"].iloc[-1])
            result["pbr"] = _num(fund["PBR"].iloc[-1])
    except Exception:
        pass
    return result


def refresh(conn, code: str) -> None:
    """시세·지표를 새로 받아 DB에 저장한다. 시세를 못 받으면 예외."""
    prices = fetch_prices(code)
    db.save_prices(conn, code, prices)
    fund = fetch_fundamentals(code, prices)
    db.save_fundamentals(conn, code, prices.index[-1].strftime("%Y-%m-%d"), fund)


def quote(prices: pd.DataFrame) -> dict | None:
    """현재가(최근 종가)와 전일 대비 등락."""
    if prices.empty:
        return None
    close = float(prices["close"].iloc[-1])
    prev = float(prices["close"].iloc[-2]) if len(prices) > 1 else close
    change = close - prev
    return {
        "date": prices.index[-1].strftime("%Y-%m-%d"),
        "close": close,
        "change": change,
        "change_pct": change / prev * 100 if prev else 0.0,
        "volume": int(prices["volume"].iloc[-1]),
    }
