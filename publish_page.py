"""data/latest.json → docs/index.html (GitHub Pages로 게시되는 주간 기사 페이지).

ChatGPT 웹 기능과 사람이 모두 읽기 쉬운 일반 웹페이지로 만든다.
- 맨 위: 수집 기간, 건수, 출처별 결과, 엑셀 내려받기 링크
- 본문: 기사 표 (구분 / 보도일자 / 매체명 / 제목 / 관련국가 / 원문 요약 / 원문링크)
"""
import html
import json
import os
import shutil
import sys
from urllib.parse import quote

REPO_RAW = "https://raw.githubusercontent.com/KIM0296/mcg-news-collector/main/data/"


def esc(s):
    return html.escape(s or "", quote=True)


def build(data_dir="data", docs_dir="docs"):
    d = json.load(open(os.path.join(data_dir, "latest.json"), encoding="utf-8"))
    os.makedirs(docs_dir, exist_ok=True)
    shutil.copy(os.path.join(data_dir, "latest.json"), os.path.join(docs_dir, "latest.json"))
    pub = d["week_start"]
    xlsx = [f for f in os.listdir(data_dir) if f.endswith(".xlsx")]
    xlsx.sort()
    latest_xlsx = xlsx[-1] if xlsx else ""
    if latest_xlsx:
        shutil.copy(os.path.join(data_dir, latest_xlsx), os.path.join(docs_dir, "latest.xlsx"))

    rows = []
    for i, a in enumerate(d["articles"], 1):
        rows.append(
            "<tr>"
            f"<td>A{i:02d}</td><td>{esc(a['구분'])}</td><td>{esc(a['보도일자'])}</td><td>{esc(a['매체명'])}</td>"
            f"<td>{esc(a['제목'])}</td><td>{esc(a['관련국가'])}</td><td>{esc(a['원문 요약'])}</td>"
            f"<td><a href=\"{esc(a['원문링크'])}\">{esc(a['원문링크'])}</a></td>"
            "</tr>")
    src = ", ".join(f"{k} {v}" for k, v in d.get("sources", {}).items())
    page = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MCG 주간 원자력 기사 DB — {esc(d['week_start'])} ~ {esc(d['week_end'])}</title>
<style>
body{{font-family:-apple-system,"Malgun Gothic","Noto Sans KR",sans-serif;margin:24px;color:#222;background:#fff}}
h1{{color:#841938;font-size:22px;margin:0 0 6px}} .meta{{color:#555;margin-bottom:14px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border:1px solid #ddd;padding:6px;vertical-align:top}}
th{{background:#841938;color:#fff;position:sticky;top:0}} tr:nth-child(even){{background:#faf7f8}}
a{{color:#801A86;word-break:break-all}} .btn{{display:inline-block;background:#841938;color:#fff;padding:6px 12px;border-radius:4px;text-decoration:none;margin-right:6px}}
</style></head><body>
<h1>MCG 주간 원자력 기사 DB</h1>
<div class="meta">
<p><b>수집 기간(week_start ~ week_end):</b> {esc(d['week_start'])} ~ {esc(d['week_end'])}<br>
<b>기사 수(count):</b> {d['count']}건 &nbsp; <b>출처별:</b> {esc(src)}</p>
<p><a class="btn" href="latest.xlsx">엑셀 내려받기</a><a class="btn" href="latest.json">JSON</a></p>
</div>
<table><thead><tr><th>ID</th><th>구분</th><th>보도일자</th><th>매체명</th><th>제목</th><th>관련국가</th><th>원문 요약</th><th>원문링크</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table>
</body></html>
"""
    open(os.path.join(docs_dir, "index.html"), "w", encoding="utf-8").write(page)
    open(os.path.join(docs_dir, ".nojekyll"), "w").write("")
    print(f"게시 페이지 생성: {docs_dir}/index.html ({d['count']}건)")


if __name__ == "__main__":
    build(*(sys.argv[1:3]))
