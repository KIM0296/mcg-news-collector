"""주간 수집 전체 흐름: 출처별 수집 → 중복 제거 → 국가 추정 → 엑셀 저장."""
import datetime as dt
import os

from . import enrich, excel
from .sources import kaif, kneiss, wnn


def week_range(monday):
    if isinstance(monday, str):
        monday = dt.date.fromisoformat(monday)
    monday = monday - dt.timedelta(days=monday.weekday())   # 어느 요일을 넣어도 그 주 월요일로
    return monday, monday + dt.timedelta(days=6)


def last_week(today=None):
    today = today or dt.date.today()
    return week_range(today - dt.timedelta(days=7))


def run(monday=None, out_dir=".", fetcher=None, sources=("kaif", "wnn", "kneiss"),
        include_notices=False, log=print):
    from .fetch import Fetcher
    start, end = week_range(monday) if monday else last_week()
    fetcher = fetcher or Fetcher()
    log(f"수집 기간: {start:%Y.%m.%d}(월) ~ {end:%Y.%m.%d}(일)")
    items, report = [], {}
    try:
        for name in sources:
            try:
                if name == "kaif":
                    got = kaif.collect(fetcher, start, end, include_notices=include_notices, log=log)
                elif name == "wnn":
                    got = wnn.collect(fetcher, start, end, log=log)
                elif name == "kneiss":
                    got = kneiss.collect(fetcher, start, end, log=log)
                else:
                    continue
                report[name] = f"{len(got)}건"
                items += got
            except kneiss.SourceNotConfigured as e:
                report[name] = "설정 전(건너뜀)"
                log(f"  {e}")
            except Exception as e:   # 한 출처가 실패해도 나머지로 엑셀을 만든다
                report[name] = f"실패: {e}"
                log(f"  {name} 수집 실패: {e}")
    finally:
        fetcher.close()

    items = enrich.dedupe(items, log=log)
    for it in items:
        if not it.country:
            it.country = enrich.guess_country(it)

    pub = start + dt.timedelta(days=7)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"국내외단신DB-MCG-{pub:%Y%m%d}.xlsx")
    excel.save(items, path, f"국내외단신DB-{start:%Y.%m}")
    jpath = os.path.join(out_dir, f"articles-{pub:%Y%m%d}.json")
    _save_json(items, jpath, start, end, report)
    log(f"저장: {path} (총 {len(items)}건)")
    return {"path": path, "count": len(items), "sources": report, "start": str(start), "end": str(end),
            "items": items}


def _save_json(items, path, start, end, report):
    """GPT 연동(Actions)용: 같은 내용을 JSON으로도 저장한다."""
    import json
    rows = [{"구분": i.category, "보도일자": i.date, "매체명": i.media, "제목": i.title,
             "핵심 키워드": i.keywords, "관련국가": i.country, "원문링크": i.url, "원문 요약": i.summary}
            for i in sorted(items, key=lambda x: (x.date, excel.CATEGORY_ORDER.get(x.category, 9)))]
    data = {"week_start": str(start), "week_end": str(end), "count": len(rows), "sources": report,
            "articles": rows}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    latest = os.path.join(os.path.dirname(path), "latest.json")
    with open(latest, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return path
