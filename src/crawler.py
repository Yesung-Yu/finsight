"""뉴스 수집 (FR-5).

수집 대상: 네이버 금융·네이버 뉴스는 robots.txt가 전체 수집을 금지(Disallow: /)하므로 사용하지 않는다.
대신 네이버 검색 API(뉴스, NAVER API HUB)로 기사 목록을 받고, 본문은 원문 언론사 페이지에서
robots.txt 허용 여부를 확인한 뒤 1초 간격으로 가져온다.
API 키는 프로젝트 최상위 .env 파일의 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 으로 설정한다.
"""
from __future__ import annotations

import html
import os
import re
import time
from email.utils import parsedate_to_datetime
from urllib import robotparser
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# 네이버 검색 API는 2026-07-31부터 개발자센터 신규 신청이 끝나고 NAVER API HUB(네이버클라우드)로 이관되었다.
# 기본은 HUB를 쓰고, 예전 개발자센터 키(2027-06-30까지 동작)는 .env 에 NAVER_API=legacy 로 쓸 수 있다.
API = {
    "hub": ("https://naverapihub.apigw.ntruss.com/search/v1/news", "X-NCP-APIGW-API-KEY-ID", "X-NCP-APIGW-API-KEY"),
    "legacy": ("https://openapi.naver.com/v1/search/news.json", "X-Naver-Client-Id", "X-Naver-Client-Secret"),
}
USER_AGENT = "FinSightBot/0.1 (student project; news summary demo)"
REQUEST_DELAY = 1.0  # 요청 사이 지연(초)
TIMEOUT = 10

# 언론사 본문 영역으로 자주 쓰이는 선택자
BODY_SELECTORS = [
    "[itemprop=articleBody]", "#articleBody", "#article-view-content-div", "#articletxt",
    "#news_body_area", "#article_body", "#articeBody", ".article_body", ".article-body",
    ".news_body", ".view_con", ".art_txt", "#textBody", ".article_txt", "#newsEndContents",
    "article",
]

_robots_cache: dict[str, robotparser.RobotFileParser | None] = {}
_last_request = 0.0


class NewsApiError(RuntimeError):
    pass


def _wait() -> None:
    global _last_request
    gap = time.monotonic() - _last_request
    if gap < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - gap)
    _last_request = time.monotonic()


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def allowed_by_robots(url: str) -> bool:
    parts = urlparse(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots_cache:
        rp = robotparser.RobotFileParser()
        try:
            resp = requests.get(base + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            if resp.status_code >= 400:
                rp = None  # robots.txt 없음 → 제한 없음
            else:
                rp.parse(resp.text.splitlines())
        except requests.RequestException:
            rp = False  # 확인 실패 → 안전하게 수집하지 않음
        _robots_cache[base] = rp
    rp = _robots_cache[base]
    if rp is None:
        return True
    if rp is False:
        return False
    return rp.can_fetch(USER_AGENT, url)


def search_news(query: str, display: int = 20, start: int = 1) -> list[dict]:
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not cid or not secret:
        raise NewsApiError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 이 .env 에 설정되지 않았습니다.")
    url, id_header, secret_header = API.get(os.getenv("NAVER_API", "hub").lower(), API["hub"])
    resp = requests.get(
        url,
        params={"query": query, "display": display, "start": start, "sort": "date"},
        headers={id_header: cid, secret_header: secret},
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise NewsApiError(f"네이버 검색 API 오류 {resp.status_code}: {resp.text[:200]}")
    try:
        data = resp.json()
    except ValueError:
        raise NewsApiError(f"네이버 검색 API 응답을 해석할 수 없습니다: {resp.text[:200]}")
    items = []
    for it in data.get("items", []):
        url = it.get("originallink") or it.get("link")
        try:
            published = parsedate_to_datetime(it["pubDate"]).strftime("%Y-%m-%d %H:%M:%S")
        except (KeyError, TypeError, ValueError):
            published = None
        items.append({
            "title": _clean(it.get("title", "")),
            "url": url,
            "published_at": published,
            "description": _clean(it.get("description", "")),
        })
    return items


def _extract_body(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "iframe", "figure", "figcaption", "table", "aside"]):
        tag.decompose()
    for sel in BODY_SELECTORS:
        node = soup.select_one(sel)
        if node:
            text = node.get_text("\n", strip=True)
            if len(text) > 200:
                return text
    # 선택자가 맞지 않으면 <p> 글자가 가장 많은 블록을 본문으로 본다
    best, best_len = "", 0
    for div in soup.find_all(["div", "section"]):
        ps = div.find_all("p", recursive=False)
        text = "\n".join(p.get_text(" ", strip=True) for p in ps)
        if len(text) > best_len:
            best, best_len = text, len(text)
    return best


def _clean_body(text: str) -> str:
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "@" in line and len(line) < 60:  # 기자 이메일 줄
            continue
        if re.search(r"무단\s*전재|재배포\s*금지|Copyright|ⓒ|©", line):
            continue
        lines.append(line)
    text = re.sub(r"\[[^\]]{0,20}기자\]|\([^)]{0,30}=\S{0,10}\)", " ", " ".join(lines))  # [홍길동 기자], (서울=연합뉴스)
    return re.sub(r"\s+", " ", text).strip()


def fetch_article(url: str) -> tuple[str | None, str | None]:
    """(언론사명, 본문). 수집할 수 없으면 (None, None)."""
    if not url or not allowed_by_robots(url):
        return None, None
    _wait()
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
        return None, None
    resp.encoding = resp.apparent_encoding if resp.encoding in (None, "ISO-8859-1") else resp.encoding
    soup = BeautifulSoup(resp.text, "lxml")
    site = soup.find("meta", property="og:site_name")
    press = site["content"].strip() if site and site.get("content") else None
    body = _clean_body(_extract_body(soup))
    return press, (body if len(body) > 100 else None)


def press_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


# 기사에서 다른 이름으로 더 많이 쓰는 종목
ALIASES = {"NAVER": ["네이버"], "LG에너지솔루션": ["LG엔솔"], "SK하이닉스": ["하이닉스"], "기아": ["기아차"]}


def _name_pattern(stock_name: str) -> re.Pattern:
    """종목명 뒤에 조사나 문장부호가 올 때만 일치한다. '카카오게임즈', '카카오맵' 같은 다른 이름은 제외."""
    names = "|".join(re.escape(n) for n in [stock_name] + ALIASES.get(stock_name, []))
    particle = "은|는|이|가|을|를|의|와|과|도|에|로|만|측|株"
    return re.compile(rf"(?:{names})(?:(?=[^가-힣A-Za-z0-9])|$|(?={particle}))", re.IGNORECASE)


def candidates(stock_name: str, items: list[dict]) -> list[dict]:
    """제목에 종목명이 있는 기사를 먼저, 부족하면 요약문에만 있는 기사를 뒤에 둔다. 둘 다 없으면 제외."""
    pattern = _name_pattern(stock_name)
    in_title, in_desc = [], []
    for it in items:
        if pattern.search(it["title"]):
            in_title.append(it)
        elif pattern.search(it["description"]):
            in_desc.append(it)
    return in_title + in_desc


SIMILAR_THRESHOLD = 0.4  # 실제 기사로 확인: 같은 사건 0.4 이상, 다른 기사 0.2 이하
# 기사 제목에 자주 쓰는 줄임말 → 원래 말 (비교할 때만 사용)
TITLE_SYNONYMS = {"유증": "유상증자", "영업익": "영업이익", "순익": "순이익", "목표가": "목표주가", "자사주": "자기주식"}


def _title_grams(title: str, stock_name: str) -> set[str]:
    """제목에서 말머리·종목명·기호를 빼고 두 글자씩 자른 조각."""
    text = re.sub(r"\[[^\]]*\]", " ", title)
    for n in [stock_name] + ALIASES.get(stock_name, []):
        text = re.sub(re.escape(n), " ", text, flags=re.IGNORECASE)
    for short, full in TITLE_SYNONYMS.items():
        text = re.sub(rf"{short}(?![가-힣])", full, text)
    text = re.sub(r"[^가-힣A-Za-z0-9]", "", text).lower()
    return {text[i:i + 2] for i in range(len(text) - 1)}


def is_similar(title_a: str, title_b: str, stock_name: str) -> bool:
    """같은 사건을 다룬 기사인지 제목으로 판단한다."""
    a, b = _title_grams(title_a, stock_name), _title_grams(title_b, stock_name)
    if not a or not b:
        return title_a == title_b
    common = len(a & b)
    if min(len(a), len(b)) < 4:  # 아주 짧은 제목은 거의 같을 때만 같은 기사로 본다
        return common / len(a | b) >= 0.8
    return common / min(len(a), len(b)) >= SIMILAR_THRESHOLD


def dedupe(items: list[dict], stock_name: str) -> list[dict]:
    """비슷한 제목의 기사를 하나로 합친다. 앞에 있는(최신) 기사를 남긴다."""
    kept: list[dict] = []
    for it in items:
        if not any(is_similar(it["title"], k["title"], stock_name) for k in kept):
            kept.append(it)
    return kept


def collect(stock_name: str, limit: int = 5, skip_url=lambda url: False) -> list[dict]:
    """종목 관련 최신 기사 limit건을 수집한다. skip_url(url)이 True면 이미 저장된 기사로 보고 건너뛴다."""
    seen, unique = set(), []
    for start in (1, 101):  # 후보가 모자라면 다음 100건까지 본다
        for query in [stock_name] + ALIASES.get(stock_name, []):
            for it in search_news(query, display=100, start=start):
                if it["url"] not in seen:
                    seen.add(it["url"])
                    unique.append(it)
        if len(dedupe(candidates(stock_name, unique), stock_name)) >= limit:
            break
    results = []
    for it in dedupe(candidates(stock_name, unique), stock_name):
        if len(results) >= limit:
            break
        if skip_url(it["url"]):
            results.append({**it, "cached": True})
            continue
        press, body = fetch_article(it["url"])
        results.append({
            **it,
            "press": press or press_from_url(it["url"]),
            "body": body or it["description"],  # 본문을 못 가져오면 API 요약 문구로 대체
            "cached": False,
        })
    return results
