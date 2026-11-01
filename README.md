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
| `KRX_ID`, `KRX_PW` | 선택 (전체 종목 검색, 시가총액·PER·PBR) | [KRX 정보데이터시스템](https://data.krx.co.kr) 무료 **일반 회원가입**(아이디·비밀번호). 네이버 등 간편로그인 계정은 pykrx 자동 로그인 불가 |

KRX 계정이 없으면 내장 시연 종목 20개만 이름으로 검색되고(6자리 코드 검색은 모든 종목 가능), 시가총액·PER·PBR은 "-"로 표시됩니다.

## 실행

### 내 PC에서 확인

```powershell
.\.venv\Scripts\streamlit.exe run app.py     # 브라우저에서 http://localhost:8501
```

처음 실행하면 요약(KoBART)·감성(KR-FinBERT) 모델을 내려받습니다(약 1분, 1.5GB 정도).
`일반 실행.bat`을 더블클릭하거나 VS Code의 `Tasks: Run Task`로도 실행할 수 있습니다.

> `.ps1` 스크립트가 "실행할 수 없습니다"라며 막히면 해당 터미널에서 먼저
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`를 입력하세요. `.bat` 파일과 VS Code 작업은 이 설정이 필요 없습니다.

## 전시 전 준비 (오프라인 시연)

```powershell
.\.venv\Scripts\python.exe scripts\warm_cache.py              # 시연 종목 20개 (인터넷 필요, 10분 안팎)
.\.venv\Scripts\python.exe scripts\warm_cache.py 삼성전자 카카오  # 원하는 종목만
```

한 번 채워 두면 인터넷 없이도 캐시된 종목의 모든 영역이 표시됩니다. 오늘 갱신한 종목은 다시 수집하지 않으므로 **시연 당일 아침에 한 번 더 실행**하세요.
캐시 DB(`data/*.db`)는 Git에 올라가지 않으니 PC를 바꾸면 다시 채워야 합니다.

## 전시 실행 (휴대폰 접속)

관람객이 QR을 스캔해 휴대폰으로 접속합니다. 전시 모드에서는 "데이터 새로고침" 버튼이 숨겨지고, 새 종목 수집은 한 번에 하나씩만 처리됩니다.

| 방식 | 명령 / 파일 | 접속 조건 |
| --- | --- | --- |
| **터널 (권장)** | `.\scripts\serve_kiosk.ps1 -Tunnel` 또는 `전시 실행(터널).bat` | PC만 인터넷에 연결되면 됩니다. 관람객은 자기 데이터로 접속합니다. |
| 핫스팟 (예비) | `.\scripts\serve_kiosk.ps1` 또는 `전시 실행(핫스팟).bat` | PC와 휴대폰이 같은 핫스팟에 연결돼야 합니다. 인터넷이 끊겨도 됩니다. |

1. 실행하면 프로젝트 폴더에 `qr.png`가 만들어집니다. 화면에 띄워 휴대폰으로 스캔합니다.
2. 끄려면 터미널에서 `Ctrl+C`를 누릅니다.

터널 모드는 [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)가 필요합니다(`winget install --id Cloudflare.cloudflared`).
터널 주소(`https://*.trycloudflare.com`)는 **스크립트를 새로 실행할 때마다 바뀝니다.** 켜 둔 동안에는 같은 QR을 계속 쓸 수 있지만, 다시 켜면 새 `qr.png`를 보여 줘야 합니다. 주소를 아는 사람은 누구나 접속할 수 있으니 시연이 끝나면 종료하세요.
핫스팟 방식은 PC를 핫스팟에 먼저 연결한 뒤 실행해야 하고, Windows 방화벽에서 개인 네트워크 접속을 허용해야 합니다.

### 시연 당일 순서

1. 아침에 인터넷을 연결하고 `warm_cache.py`를 실행합니다.
2. PC를 인터넷(또는 핫스팟)에 연결하고 `전시 실행(터널).bat`을 실행합니다.
3. `qr.png`를 띄우고 휴대폰 데이터로 한 번 접속해 봅니다.
4. 시연 중에는 PC 절전과 화면 꺼짐을 막고 충전기를 연결해 둡니다.

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
| `scripts/serve_kiosk.ps1` | 전시 모드 실행 (핫스팟 / `-Tunnel`) |
| `scripts/make_qr.py` | 접속 주소 QR(`qr.png`) 생성 |
| `*.bat`, `.vscode/tasks.json` | 더블클릭·VS Code 실행 바로가기 |
