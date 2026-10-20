"""MCG 주간 원자력 기사 수집기 — 실행 파일.

사용법
  python collect.py                     # 지난주(월~일) 기사 수집
  python collect.py --week 2026-05-04   # 특정 주 (그 주의 아무 날짜나 가능)
  python collect.py --out 저장폴더
  python collect.py --only wnn          # 특정 출처만 (kaif, wnn, kneiss)
  python collect.py --notices           # KAIF '원자력계 소식'(공지·행사)도 포함

결과: 국내외단신DB-MCG-YYYYMMDD.xlsx  →  MCG 주간 브리프 GPT에 첨부하고 "시작"
"""
import argparse
import sys

from mcg_collect import pipeline
from mcg_collect.fetch import Fetcher


def main(argv=None):
    p = argparse.ArgumentParser(description="MCG 주간 원자력 기사 수집기")
    p.add_argument("--week", help="수집할 주의 날짜 (YYYY-MM-DD). 생략하면 지난주")
    p.add_argument("--out", default=".", help="엑셀 저장 폴더")
    p.add_argument("--only", nargs="+", choices=["kaif", "wnn", "kneiss"], help="수집할 출처만 지정")
    p.add_argument("--notices", action="store_true", help="KAIF 원자력계 소식 포함")
    p.add_argument("--fixtures", help="(시험용) 저장된 HTML 폴더로 실행")
    p.add_argument("--cache", help="(선택) 받은 페이지를 저장해 두는 폴더 — 다시 실행할 때 빠름")
    a = p.parse_args(argv)

    fetcher = Fetcher(fixtures_dir=a.fixtures, cache_dir=a.cache)
    r = pipeline.run(a.week, a.out, fetcher, sources=a.only or ("kaif", "wnn", "kneiss"),
                     include_notices=a.notices)
    print("\n출처별 결과:", ", ".join(f"{k} {v}" for k, v in r["sources"].items()))
    print(f"완료: {r['path']}")
    return 0 if r["count"] else 1


if __name__ == "__main__":
    sys.exit(main())
