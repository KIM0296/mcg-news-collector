"""수집 결과 한 건(기사)의 공통 형식."""
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit


@dataclass
class Item:
    category: str          # 구분: 국내기사 / 세계기사 / 사설/칼럼/기고 / WNN / 원자력계소식 / 해외단신
    date: str              # 보도일자 YYYY.MM.DD
    media: str             # 매체명
    title: str             # 제목
    url: str               # 원문링크
    keywords: str = ""     # 핵심 키워드 (비워 두면 GPT가 채움)
    country: str = ""      # 관련국가
    summary: str = ""      # 원문 요약(첫 문단). 근거 확인용
    source: str = ""       # 수집 출처: KAIF / WNN / K-NEISS
    extra: dict = field(default_factory=dict)

    def key(self):
        return normalize_url(self.url)


def normalize_url(url: str) -> str:
    if not url:
        return ""
    p = urlsplit(url.strip())
    host = p.netloc.lower().removeprefix("www.")
    path = p.path.rstrip("/")
    # 네이버·언론사 추적용 꼬리표 제거
    keep = "&".join(q for q in p.query.split("&") if q and not q.startswith(("ref=", "input=", "utm_", "sid=")))
    return urlunsplit(("https", host, path, keep, ""))
