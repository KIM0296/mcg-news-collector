"""World Nuclear News 수집.

사이트맵(https://world-nuclear-news.org/sitemap.xml)에서 기간 내 기사 주소를 찾고,
기사마다 제목·분류·발행시각·첫 문단 요약(og:description)을 읽는다.
"""
import datetime as dt
import html as _html
import re

from bs4 import BeautifulSoup

from ..model import Item

SITEMAP = "https://world-nuclear-news.org/sitemap.xml"
SKIP_SECTIONS = {"Podcasts & Features"}


def list_articles(fetcher, start, end):
    xml = fetcher.get(SITEMAP, timeout=90)
    urls = []
    for loc, mod in re.findall(r"<loc>([^<]+/articles/[^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", xml):
        try:
            d = dt.date.fromisoformat(mod[:10])
        except ValueError:
            continue
        if start - dt.timedelta(days=2) <= d <= end + dt.timedelta(days=2):   # 수정일 차이 여유
            urls.append(loc.strip())
    return urls


def _clean(text):
    """HTML 기호(&#39; &nbsp; 등)와 끝의 ';' 찌꺼기를 정리한다."""
    for _ in range(2):
        text = _html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"[\s;]+$", "", text)


def parse_article(html, url):
    s = BeautifulSoup(html, "html.parser")

    def meta(prop):
        m = s.find("meta", attrs={"property": prop}) or s.find("meta", attrs={"name": prop})
        return _clean(m.get("content") or "") if m else ""

    title = meta("og:title") or (s.find("h1").get_text(strip=True) if s.find("h1") else "")
    published = meta("article:published_time")[:10]
    return {
        "title": title,
        "section": meta("article:section"),
        "date": published,
        "summary": meta("og:description") or meta("description"),
        "url": meta("og:url") or url,
    }


def collect(fetcher, start, end, log=print):
    urls = list_articles(fetcher, start, end)
    out, skipped = [], 0
    for u in urls:
        try:
            a = parse_article(fetcher.get(u), u)
        except Exception as e:  # 기사 하나가 실패해도 나머지는 계속
            log(f"    WNN 읽기 실패: {u} ({e})")
            continue
        if not a["date"]:
            continue
        d = dt.date.fromisoformat(a["date"])
        if not (start <= d <= end):
            continue
        if a["section"] in SKIP_SECTIONS:
            skipped += 1
            continue
        out.append(Item(category="WNN", date=d.strftime("%Y.%m.%d"), media="World Nuclear News",
                        title=a["title"], url=a["url"], summary=a["summary"], source="WNN",
                        extra={"section": a["section"]}))
    log(f"  WNN 기사 {len(out)}건 (팟캐스트·특집 {skipped}건 제외)")
    return sorted(out, key=lambda i: i.date)
