# FinSight

1인 학술제 전시용 프로젝트. 주식 뉴스 3줄 요약, 호재·악재 판정, pykrx 시세를 한 화면에 보여 주는 Streamlit 웹사이트.
기능 요구사항과 WBS는 [요구사항.md](요구사항.md), 설치·실행은 [README.md](README.md)를 따른다. 결정을 바꾸면 이 파일도 고친다.

## 명령 (Windows, Python 3.11)

```powershell
.\.venv\Scripts\streamlit.exe run app.py        # http://localhost:8501
.\.venv\Scripts\python.exe -m pytest            # tests/test_core.py
.\.venv\Scripts\python.exe scripts\warm_cache.py  # 시연 종목 10개 캐시 채우기
```

## 지켜야 할 것

- `.env`(API 키, KRX 계정)와 `data/*.db`는 Git에 올리지 않는다. 이 레포는 **Public**이므로 키 값을 코드, 문서, 커밋 메시지에 쓰지 않는다.
- 오프라인 시연은 필수다. 인터넷 없이도 캐시된 종목의 모든 영역이 표시되어야 한다.
- 투자 추천이나 매수·매도 신호를 제공하지 않는다. 화면 하단 면책 문구를 유지한다.
- 국내 증시 관례대로 상승은 빨강 `#d6293e` ▲, 하락은 파랑 `#1e5bd6` ▼, 보합은 회색 `#8a8f98`로 표시한다.
- 화면 제목은 "주식 뉴스 요약 · 투자 보조"이고 FinSight 로고는 넣지 않는다.

## 주요 결정과 이유

### 뉴스 수집
- finance.naver.com과 n.news.naver.com은 robots.txt가 `Disallow: /`라서 크롤링하지 않는다.
- 네이버 개발자센터는 2026-07-31부터 검색 API 신규 신청을 받지 않아 **NAVER API HUB**를 쓴다.
  - 엔드포인트: `https://naverapihub.apigw.ntruss.com/search/v1/news`
  - 헤더: `X-NCP-APIGW-API-KEY-ID`, `X-NCP-APIGW-API-KEY`
  - 예전 개발자센터 키는 `NAVER_API=legacy`로 쓸 수 있다.
- 본문은 언론사 원문 페이지에서 도메인별 robots.txt를 확인한 뒤 1초 간격으로 가져온다. 본문을 못 얻으면 API의 description을 쓴다.

### 시세와 지표 (pykrx 1.2.x)
- OHLCV는 로그인 없이 된다. 종목 목록, 시가총액, PER, PBR은 KRX 로그인이 필요하다.
- pykrx는 import 시점에 환경 변수 `KRX_ID`, `KRX_PW`를 읽는다. 그래서 `src/market.py`가 import 전에 프로젝트 루트의 `.env`를 경로를 지정해 불러온다.
- 아이디·비밀번호 로그인만 지원하므로 네이버 간편로그인 계정은 쓸 수 없고 **KRX 일반회원 계정**이 필요하다.
- KRX 계정이 없으면 내장 시연 종목 10개만 이름으로 검색되고 지표는 "-"로 표시된다.

### 모델
- 요약: `gogamza/kobart-summarization` (입력 최대 1024토큰, 3줄 이내)
- 감성: `snunlp/KR-FinBert-SC` (negative/neutral/positive를 악재/중립/호재로 표시)
- 오프라인에서도 뜨도록 `local_files_only=True`로 먼저 불러온다.

### 관련성과 중복 제거 (`src/crawler.py`)
- 제목에 종목명이 있는 기사를 먼저 고른다. 종목명 경계를 정규식으로 검사해 "카카오게임즈" 같은 더 긴 이름을 걸러 낸다. 별칭은 `ALIASES`에 있다.
- 비슷한 제목은 동의어(`TITLE_SYNONYMS`)를 맞춘 뒤 글자 2-gram 겹침이 0.4 이상이면 같은 기사로 합친다.

### 캐시와 오프라인 (`src/service.py`)
- SQLite에 저장한다. 오늘 갱신한 종목은 다시 수집하지 않는다.
- 연결 확인은 1초 제한의 소켓 검사로 한다. 실패한 종목은 10분 동안 재시도하지 않는다.

## 구현 시 주의

- `save_prices`에서 값을 `float`/`int`로 변환한다. numpy 정수를 그대로 넣으면 SQLite에 blob으로 저장된다.
- Streamlit의 `use_container_width`는 지원 중단되었으므로 `width="stretch"`를 쓴다.
- `AppTest.from_file`에는 절대 경로를 넘긴다.
- 사이드바의 저장 종목 목록은 수집이 끝난 뒤 그려야 해서 `app.py`의 `finish()`에서 채운다.

## 남은 작업

- 포스터용 화면 캡처 (사용자)
- 산출물 문서 초안: 설계서, 사용자 지침서
- 선택 개선: 요약 길이, 신뢰도 문구, 합쳐진 비슷한 기사 수 표시
