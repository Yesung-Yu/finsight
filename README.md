# 주식 뉴스 요약 · 투자 보조 (FinSight)

종목을 한 번 검색하면 시세·지표·차트, 최신 뉴스 3줄 요약, 호재·악재 판정을 한 화면에서 보여 주는 Streamlit 웹사이트입니다.
요구사항은 [요구사항.md](요구사항.md)를 참고하세요.

## 설치 (Windows 11, Python 3.11)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env   # 메모장으로 열어 API 키 입력
```

| 설정 | 필요 여부 | 발급처 |
| --- | --- | --- |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 필수 (뉴스 수집) | [네이버클라우드 플랫폼](https://www.ncloud.com) 가입 → 콘솔의 NAVER API HUB → Application 등록 → "검색" API 선택 (개발자센터는 2026-07-31부터 검색 API 신규 신청 불가) |
| `KRX_ID`, `KRX_PW` | 선택 (전체 종목 검색, 시가총액·PER·PBR) | [KRX 정보데이터시스템](https://data.krx.co.kr) 무료 회원가입 |

KRX 계정이 없으면 내장 시연 종목 10개만 이름으로 검색되고(6자리 코드 검색은 모든 종목 가능), 시가총액·PER·PBR은 "-"로 표시됩니다.

## 실행

```powershell
.\.venv\Scripts\streamlit.exe run app.py     # 브라우저에서 http://localhost:8501
```

처음 실행하면 요약(KoBART)·감성(KR-FinBERT) 모델을 내려받습니다(약 1분, 1.5GB 정도).

## 전시 전 준비 (오프라인 시연)

```powershell
.\.venv\Scripts\python.exe scripts\warm_cache.py              # 시연 종목 10개
.\.venv\Scripts\python.exe scripts\warm_cache.py 삼성전자 카카오  # 원하는 종목만
```

한 번 채워 두면 인터넷 없이도 시연 종목의 모든 영역이 표시되며, 화면에 "저장된 데이터 (날짜 기준)"이 나타납니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 구조

| 파일 | 역할 |
| --- | --- |
| `app.py` | 메인 화면 (검색, 2단 레이아웃, 사이드바) |
| `src/market.py` | pykrx 시세·지표 (FR-1~4) |
| `src/crawler.py` | 네이버 검색 API + 언론사 본문 수집 (FR-5) |
| `src/summarizer.py` | KoBART 3줄 요약 (FR-6) |
| `src/sentiment.py` | KR-FinBERT 호재·중립·악재 판정 (FR-7) |
| `src/service.py` | 수집·분석·캐시 통합 (FR-8) |
| `src/db.py` | SQLite (`data/finsight.db`) |
| `src/ui.py` | 화면 구성 요소 |
| `scripts/warm_cache.py` | 시연 데이터 미리 채우기 |
