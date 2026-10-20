"""KAIF(한국원자력산업협회) 투데이뉴스 수집.

게시판: https://www.kaif.or.kr/ko/?c=250  (평일마다 1건, 1쪽 20건)
게시물 하나 = 그날의 뉴스레터. 안에 '국내', '해외', '사설/칼럼', '원자력계 소식' 섹션이 있고
각 섹션은 [· 기사제목(링크) 매체명] 이 반복된다.
"""
import datetime as dt
import re

from bs4 import BeautifulSoup, NavigableString

from ..model import Item

LIST_URL = "https://www.kaif.or.kr/ko/?c=250&s=&gbn=list&gp={page}"
VIEW_URL = "https://www.kaif.or.kr/ko/?c=250&s=&gp=1&gbn=view&ix={ix}"

# 2026년 상반기: 국내기사/세계기사/사설/칼럼/기고, 9월 이후: 국내/해외/사설/칼럼 — 둘 다 인식
SECTION_MAP = {"국내": "국내기사", "국내기사": "국내기사", "해외": "세계기사", "세계기사": "세계기사",
               "해외기사": "세계기사", "사설/칼럼": "사설/칼럼/기고", "사설/칼럼/기고": "사설/칼럼/기고",
               "사설·칼럼": "사설/칼럼/기고"}
STOP_TEXT = ("본 메일은", "지난 뉴스는")


def _date(s):
    return dt.datetime.strptime(s.strip(), "%Y.%m.%d").date()


def list_posts(fetcher, start, end, max_pages=30):
    """start~end(날짜 포함) 사이 게시물의 (날짜, ix, 제목) 목록."""
    found = []
    for page in range(1, max_pages + 1):
        html = fetcher.get_rendered(LIST_URL.format(page=page), "table.bbs-standard")
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table.bbs-standard tbody tr")
        if not rows:
            break
        oldest = None
        for tr in rows:
            a = tr.select_one("td.col-tit a")
            d = tr.select_one("td.col-date")
            if not a or not d:
                continue
            m = re.search(r"ix=(\d+)", a.get("href", ""))
            day = _date(d.get_text())
            oldest = day
            if m and start <= day <= end:
                found.append((day, int(m.group(1)), a.get_text(" ", strip=True)))
        if oldest is not None and oldest < start:
            break
    return sorted(found)


def parse_post(html, day, include_notices=False):
    """게시물 HTML에서 기사 목록을 뽑는다."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one("#bbsContents") or soup
    items, section, pending, prev_text = [], None, None, ""

    for el in body.descendants:
        if getattr(el, "name", None) == "a":
            text = el.get_text(" ", strip=True)
            href = (el.get("href") or "").strip()
            if text in SECTION_MAP:              # 섹션 머리 링크
                section, pending = SECTION_MAP[text], None
                continue
            if section and text and href.startswith("http") and "kaif.or.kr" not in href:
                pending = Item(category=section, date=day.strftime("%Y.%m.%d"), media="",
                               title=text, url=href, source="KAIF")
                items.append(pending)
        elif isinstance(el, NavigableString):
            if el.parent is not None and el.parent.name == "a":
                continue
            t = el.strip()
            if not t or t in ("·", "|"):
                continue
            if any(t.startswith(s) for s in STOP_TEXT):
                break
            if t == "소식" and prev_text == "원자력계":
                section = "원자력계소식" if include_notices else None
                pending = None
            elif t in ("overseas", "news", "국내뉴스 리스트", "국내외", "뉴스"):
                pass
            elif pending is not None and not pending.media and t != pending.title:
                pending.media = t                 # 기사 링크 바로 뒤 텍스트 = 매체명
                pending = None
            prev_text = t
    return items


def collect(fetcher, start, end, include_notices=False, log=print):
    posts = list_posts(fetcher, start, end)
    log(f"  KAIF 게시물 {len(posts)}건: " + ", ".join(f"{d:%m/%d}(ix={ix})" for d, ix, _ in posts))
    out = []
    for day, ix, _ in posts:
        html = fetcher.get_rendered(VIEW_URL.format(ix=ix), "#bbsContents")
        got = parse_post(html, day, include_notices)
        log(f"    {day:%m/%d}: 기사 {len(got)}건")
        out += got
    return out
