"""전시 전 시연 종목의 시세·뉴스·요약·판정을 미리 채운다 (FR-8).

실행: python scripts/warm_cache.py            # 시연 종목 10개 + 추가 종목 10개
      python scripts/warm_cache.py 삼성전자 카카오  # 원하는 종목만
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db, market, service  # noqa: E402


def main(queries: list[str]) -> None:
    conn = db.connect()
    print(f"종목 목록 {market.ensure_stock_list(conn)}개 준비")
    print("모델 불러오는 중...")
    summarizer, analyzer = service.load_models()
    if summarizer is None or analyzer is None:
        print("! 모델을 불러오지 못했습니다. 인터넷 연결을 확인하세요.")
    targets = queries or [name for _, name, _ in market.DEMO_STOCKS + market.WARM_EXTRA_STOCKS]
    for q in targets:
        stock = market.resolve(conn, q)
        if stock is None:
            print(f"- {q}: 종목을 찾을 수 없음")
            continue
        t = time.time()
        errors = service.update_stock(conn, stock, summarizer, analyzer)
        news = service.latest_news(conn, stock["code"])
        analyzed = sum(1 for n in news if n["summary"] is not None)
        status = "OK" if not errors else "; ".join(errors)
        print(f"- {stock['name']}({stock['code']}): 시세 {len(db.load_prices(conn, stock['code']))}일, "
              f"뉴스 {len(news)}건(분석 {analyzed}) [{time.time() - t:.0f}초] {status}")


if __name__ == "__main__":
    main(sys.argv[1:])
