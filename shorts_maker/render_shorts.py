"""MCG 쇼츠 영상 자동 조립기.

입력: 브리프 플러그인이 만든 쇼츠 대본 엑셀 (MCG_Shorts_YYYYMMDD.xlsx)
출력: 쇼츠 영상 mp4 5개 (세로 1080×1920, 자막 + 배경음악, 내레이션 없음)

화면 틀은 샘플 쇼츠(2026-04-06)를 측정해 그대로 재현한다.
  - 남색 바탕(#102F66), 오른쪽 위 로고
  - 제목 1줄: 하늘색 상자(#B3DDEB), 제목 2줄: 흰색 상자
  - 가운데 영상 영역 y=452~1472 (자료 영상: Pexels, 키가 없으면 단색 배경)
  - 영상 아래쪽 반투명 자막 띠, 강조 단어는 노란색
  - 아래 날짜 상자 + '원자력 정책 동향', 마지막 화면 2초

사용법:
  python render_shorts.py 대본.xlsx 출력폴더
  (환경변수 PEXELS_API_KEY 가 있으면 자료 영상을 자동으로 찾아 넣는다)
"""
import datetime as dt
import glob
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import wave

import requests
from openpyxl import load_workbook
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
NAVY = (16, 47, 102)
TITLE1_BG = (179, 221, 235)
TITLE_TEXT = (16, 40, 92)
YELLOW = (255, 214, 64)
VIDEO_TOP, VIDEO_BOTTOM = 452, 1472
FPS = 30
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")


# ---------- 글꼴 ----------
def _font(weight, size):
    cands = {
        "black": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"],
        "bold": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"],
        "medium": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"],
        "light": ["/usr/share/fonts/opentype/noto/NotoSansCJK-Light.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"],
    }[weight]
    for p in cands + glob.glob("/usr/share/fonts/**/NotoSansCJK*.ttc", recursive=True):
        if os.path.exists(p):
            return ImageFont.truetype(p, size, index=1)   # index 1 = KR
    raise RuntimeError("한글 글꼴(Noto Sans CJK)이 없습니다: apt-get install fonts-noto-cjk")


# ---------- 대본 읽기 ----------
def load_script(xlsx_path):
    wb = load_workbook(xlsx_path, data_only=True)
    if "_data" in wb.sheetnames:
        ws = wb["_data"]
        raw = "".join(str(c.value or "") for c in ws["A"])
        return json.loads(raw)
    # _data 시트가 없으면 보이는 시트에서 읽는다
    m = re.search(r"(\d{8})", os.path.basename(xlsx_path))
    pub = dt.datetime.strptime(m.group(1), "%Y%m%d").date() if m else dt.date.today()
    shorts = []
    for name in wb.sheetnames:
        if not name.startswith("쇼츠"):
            continue
        ws = wb[name]
        head = str(ws["A1"].value or "")
        t = re.match(r"\[쇼츠 \d+\]\s*(.*?)\s*/\s*(.*)$", head)
        hl = re.search(r"강조 단어\(노란색\):\s*([^|]*)", str(ws["A2"].value or ""))
        lines = []
        for row in ws.iter_rows(min_row=5, values_only=True):
            if not row or row[0] in (None, "") or not str(row[0]).isdigit():
                if lines:
                    break
                continue
            lines.append({"stage": row[1], "text": str(row[2] or ""), "sec": float(row[3] or 3),
                          "scene": row[4] or "", "query": row[5] or ""})
        shorts.append({"title1": t.group(1) if t else "", "title2": t.group(2) if t else "",
                       "highlight": [h.strip() for h in (hl.group(1) if hl else "").split(",") if h.strip()],
                       "lines": lines})
    if not shorts or not any(sh["lines"] for sh in shorts):
        raise SystemExit(f"[형식 오류] {os.path.basename(xlsx_path)}: 쇼츠 대본 형식(시트 '목록·쇼츠1~5·_data')이 아닙니다. "
                         f"지금 시트: {wb.sheetnames}. 플러그인에서 '쇼츠 다시'를 입력해 다시 만든 엑셀을 올려 주세요.")
    return {"pub_date": str(pub), "shorts": shorts}


# ---------- 화면 틀 그리기 ----------
def _text_w(draw, text, font):
    return draw.textbbox((0, 0), text, font=font)[2]


def draw_frame(title1, title2, date_text, caption, highlights):
    """영상 영역(y 452~1472)은 투명, 나머지는 샘플과 같은 틀."""
    img = Image.new("RGBA", (W, H), NAVY + (255,))
    d = ImageDraw.Draw(img)
    # 영상 영역 비우기
    d.rectangle([0, VIDEO_TOP, W, VIDEO_BOTTOM], fill=(0, 0, 0, 0))
    # 로고
    logo_p = os.path.join(ASSETS, "logo_navy.png")
    if os.path.exists(logo_p):
        logo = Image.open(logo_p).convert("RGBA")
        logo = logo.resize((int(logo.width * 0.9), int(logo.height * 0.9)))
        img.alpha_composite(logo, (W - logo.width - 20, 22))
    # 제목 1줄 (하늘색 상자)
    f1 = _font("black", 70)
    tw = _text_w(d, title1, f1)
    d.rectangle([57, 133, 57 + tw + 36, 239], fill=TITLE1_BG)
    d.text((57 + 18, 186), title1, font=f1, fill=TITLE_TEXT, anchor="lm")
    # 제목 2줄 (흰색 상자) — 길면 글자 크기 줄임
    size = 70
    f2 = _font("black", size)
    while _text_w(d, title2, f2) > W - 120 - 36 and size > 44:
        size -= 2
        f2 = _font("black", size)
    tw = _text_w(d, title2, f2)
    d.rectangle([60, 278, 60 + tw + 36, 379], fill=(253, 253, 253))
    d.text((60 + 18, 329), title2, font=f2, fill=TITLE_TEXT, anchor="lm")
    # 날짜 상자 + 하단 문구
    fd = _font("light", 40)
    d.rectangle([368, 1556, 711, 1654], outline=(220, 226, 238), width=3)
    d.text((W // 2, 1605), date_text, font=fd, fill=(235, 238, 245), anchor="mm")
    d.text((W // 2, 1722), "원자력 정책 동향", font=_font("bold", 40), fill=(255, 255, 255), anchor="mm")
    # 자막 띠 + 자막 (강조 단어는 노란색)
    if caption:
        bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bar)
        bd.rectangle([60, 1290, 1020, 1396], fill=(30, 30, 30, 165))
        img.alpha_composite(bar)
        fc = _font("medium", 40)
        while _text_w(d, caption, fc) > 920 and fc.size > 28:
            fc = _font("medium", fc.size - 2)
        segs = _split_highlight(caption, highlights)
        total = sum(_text_w(d, s, fc) for s, _ in segs)
        x = (W - total) // 2
        for s, hl in segs:
            d.text((x, 1343), s, font=fc, fill=YELLOW if hl else (255, 255, 255), anchor="lm")
            x += _text_w(d, s, fc)
    return img


def _split_highlight(text, highlights):
    marks = sorted({h for h in highlights if h and h in text}, key=len, reverse=True)
    if not marks:
        return [(text, False)]
    pat = re.compile("(" + "|".join(re.escape(m) for m in marks) + ")")
    out = []
    for part in pat.split(text):
        if part:
            out.append((part, part in marks))
    return out


def draw_outro(pub):
    img = Image.new("RGBA", (W, H), NAVY + (255,))
    d = ImageDraw.Draw(img)
    label = f"{pub.year}년 {pub.month}월"
    fl = _font("black", 66)
    tw = _text_w(d, label, fl)
    d.rectangle([(W - tw) // 2 - 24, 860, (W + tw) // 2 + 24, 950], fill=TITLE1_BG)
    d.text((W // 2, 905), label, font=fl, fill=TITLE_TEXT, anchor="mm")
    d.text((W // 2, 1030), "원자력 정책 동향", font=_font("bold", 72), fill=(255, 255, 255), anchor="mm")
    logo_p = os.path.join(ASSETS, "logo_navy.png")
    if os.path.exists(logo_p):
        logo = Image.open(logo_p).convert("RGBA")
        img.alpha_composite(logo, ((W - logo.width) // 2, 1640))
    return img


# ---------- 자료 영상 (Pexels) ----------
class ClipSource:
    """자료 영상·사진 찾기. 순서: ① MCG 자체 모음(assets/clips) ② Pixabay ③ Pexels ④ 없음(남색 배경)"""
    MEDIA_EXT = (".mp4", ".mov", ".jpg", ".jpeg", ".png", ".webp")

    def __init__(self, cache_dir):
        self.pixabay = os.environ.get("PIXABAY_API_KEY", "").strip()
        self.pexels = os.environ.get("PEXELS_API_KEY", "").strip()
        self.cache = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.used = set()
        lib = os.path.join(ASSETS, "clips")
        self.library = sorted(glob.glob(os.path.join(lib, "**", "*"), recursive=True)) if os.path.isdir(lib) else []
        self.library = [f for f in self.library if f.lower().endswith(self.MEDIA_EXT)]

    def describe(self):
        parts = []
        if self.library:
            parts.append(f"자체 모음 {len(self.library)}개")
        if self.pixabay:
            parts.append("Pixabay")
        if self.pexels:
            parts.append("Pexels")
        return " + ".join(parts) or "없음(남색 배경)"

    @staticmethod
    def _tokens(text):
        return {w for w in re.split(r"[^0-9a-zA-Z가-힣]+", (text or "").lower()) if len(w) >= 2}

    def from_library(self, query):
        """파일 이름에 검색어 단어가 가장 많이 들어 있는 자료를 고른다. 예: cooling-tower_냉각탑.mp4"""
        q = self._tokens(query)
        if not q or not self.library:
            return None
        best, score = None, 0
        for f in self.library:
            name = self._tokens(os.path.splitext(os.path.basename(f))[0])
            sc = len(q & name) - (0.5 if f in self.used else 0)
            if sc > score:
                best, score = f, sc
        if best:
            self.used.add(best)
        return best

    def _download(self, url, name):
        path = os.path.join(self.cache, name)
        if not os.path.exists(path):
            with requests.get(url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                with open(path, "wb") as out:
                    for chunk in resp.iter_content(1 << 20):
                        out.write(chunk)
        return path

    def from_pixabay(self, query):
        r = requests.get("https://pixabay.com/api/videos/",
                         params={"key": self.pixabay, "q": query, "per_page": 10, "safesearch": "true"}, timeout=30)
        r.raise_for_status()
        for h in r.json().get("hits", []):
            vid = f"pixabay_{h['id']}"
            if vid in self.used:
                continue
            v = h.get("videos", {})
            f = v.get("medium") or v.get("large") or v.get("small")
            if not f or not f.get("url"):
                continue
            self.used.add(vid)
            return self._download(f["url"], vid + ".mp4")
        return None

    def from_pexels(self, query):
        r = requests.get("https://api.pexels.com/videos/search",
                         params={"query": query, "orientation": "landscape", "size": "medium", "per_page": 8},
                         headers={"Authorization": self.pexels}, timeout=30)
        r.raise_for_status()
        for v in r.json().get("videos", []):
            vid = f"pexels_{v['id']}"
            if vid in self.used:
                continue
            files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and (f.get("width") or 0) >= 1280]
            if not files:
                continue
            self.used.add(vid)
            return self._download(sorted(files, key=lambda f: f["width"])[0]["link"], vid + ".mp4")
        return None

    def get(self, query):
        if not query:
            return None
        hit = self.from_library(query)
        if hit:
            return hit
        for name, fn, key in (("Pixabay", self.from_pixabay, self.pixabay), ("Pexels", self.from_pexels, self.pexels)):
            if not key:
                continue
            try:
                hit = fn(query)
                if hit:
                    return hit
            except Exception as ex:
                print(f"    {name} 검색 실패({query}): {ex}")
        return None


# ---------- 배경음악 ----------
def make_bgm(path, seconds):
    """저작권 걱정 없는 잔잔한 배경음(화음 패드)을 직접 합성한다. assets/bgm.mp3가 있으면 그걸 쓴다."""
    sr = 44100
    try:
        import numpy as np
        t = np.arange(int(sr * seconds)) / sr
        chords_np = [(220.0, 277.18, 329.63), (196.0, 246.94, 293.66), (174.61, 220.0, 261.63), (196.0, 246.94, 329.63)]
        idx = (t // 4).astype(int) % 4
        s = np.zeros_like(t)
        for k, ch in enumerate(chords_np):
            m = idx == k
            for f in ch:
                s[m] += np.sin(2 * np.pi * f * t[m]) + 0.3 * np.sin(4 * np.pi * f * t[m])
        s /= 6
        env = 0.5 - 0.5 * np.cos(2 * np.pi * ((t % 4) / 4))
        s *= 0.35 + 0.65 * env
        fade = np.minimum(1.0, np.minimum(t / 2, (seconds - t) / 3))
        v = (np.clip(s * fade * 0.5, -1, 1) * 32767).astype("<i2")
        stereo = np.repeat(v, 2)
        with wave.open(path, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr)
            w.writeframes(stereo.tobytes())
        return path
    except ImportError:
        pass
    chords = [(220.0, 277.18, 329.63), (196.0, 246.94, 293.66), (174.61, 220.0, 261.63), (196.0, 246.94, 329.63)]
    n = int(sr * seconds)
    frames = bytearray()
    for i in range(n):
        t = i / sr
        ch = chords[int(t // 4) % len(chords)]
        env = 0.5 - 0.5 * math.cos(2 * math.pi * ((t % 4) / 4))       # 4초마다 부드럽게 오르내림
        s = sum(math.sin(2 * math.pi * f * t) + 0.3 * math.sin(4 * math.pi * f * t) for f in ch) / 6
        s *= 0.35 + 0.65 * env
        fade = min(1.0, t / 2, (seconds - t) / 3)
        v = int(max(-1, min(1, s * fade * 0.5)) * 32767)
        frames += v.to_bytes(2, "little", signed=True) * 2
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    return path


# ---------- 조립 ----------
def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-1500:])


_GRAD = None


def _gradient():
    """자료 영상 대신 쓸 넓은 남색 그라데이션 이미지 (한 번만 만든다)."""
    global _GRAD
    if _GRAD and os.path.exists(_GRAD):
        return _GRAD
    vh = VIDEO_BOTTOM - VIDEO_TOP
    gw = W * 2
    img = Image.new("RGB", (gw, vh))
    px = img.load()
    for x in range(gw):
        for y in range(0, vh, 2):
            a = math.sin(2 * math.pi * (x / gw * 1.5 + y / vh * 0.5))
            b = math.sin(2 * math.pi * (y / vh - x / gw))
            c = (int(30 + 14 * a), int(62 + 14 * b), int(125 + 18 * a * b))
            px[x, y] = c
            if y + 1 < vh:
                px[x, y + 1] = c
    _GRAD = os.path.join(tempfile.gettempdir(), "mcg_gradient.png")
    img.save(_GRAD)
    return _GRAD


def render_segment(frame_png, clip, sec, out):
    vh = VIDEO_BOTTOM - VIDEO_TOP
    if clip and clip.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):   # 사진: 천천히 옆으로 흘림
        inputs = ["-loop", "1", "-framerate", str(FPS), "-i", clip]
        vid = (f"[1:v]scale={int(W * 1.15)}:{int(vh * 1.15)}:force_original_aspect_ratio=increase,"
               f"crop={W}:{vh}:x='(iw-ow)*t/{max(sec, 1)}':y='(ih-oh)/2',setsar=1[v]")
    elif clip:
        inputs = ["-stream_loop", "-1", "-i", clip]
        vid = f"[1:v]scale={W}:{vh}:force_original_aspect_ratio=increase,crop={W}:{vh},setsar=1,fps={FPS}[v]"
    else:   # 자료 영상이 없으면 미리 그린 남색 그라데이션을 천천히 흘려보냄
        inputs = ["-loop", "1", "-framerate", str(FPS), "-i", _gradient()]
        vid = f"[1:v]crop={W}:{vh}:x='min(t*12,{W})':y=0,setsar=1[v]"
    fc = (f"[0:v]scale={W}:{H}[bg];{vid};[bg][v]overlay=0:{VIDEO_TOP}[b];"
          f"[2:v]format=rgba[fr];[b][fr]overlay=0:0,format=yuv420p[out]")
    _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x102F66:s={W}x{H}:r={FPS}:d={sec}",
          *inputs, "-loop", "1", "-i", frame_png, "-filter_complex", fc, "-map", "[out]",
          "-t", f"{sec}", "-r", str(FPS), "-c:v", "libx264", "-preset", "superfast", "-crf", "22", "-an", out])


def render_short(short, pub, out_path, clips, work):
    date_text = pub.strftime("%Y-%m-%d")
    segs = []
    last_clip = None
    for i, line in enumerate(short["lines"], 1):
        sec = max(1.5, float(line.get("sec") or 3))
        frame = draw_frame(short["title1"], short["title2"], date_text, line["text"], short.get("highlight", []))
        fp = os.path.join(work, f"f{i:02d}.png")
        frame.save(fp)
        clip = clips.get(line.get("query")) or last_clip
        last_clip = clip
        seg = os.path.join(work, f"s{i:02d}.mp4")
        render_segment(fp, clip, sec, seg)
        segs.append(seg)
    # 마지막 화면 2초
    op = os.path.join(work, "outro.png")
    draw_outro(pub).save(op)
    outro = os.path.join(work, "outro.mp4")
    _run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", op, "-t", "2", "-r", str(FPS),
          "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", outro])
    segs.append(outro)
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        f.writelines(f"file '{s}'\n" for s in segs)
    silent = os.path.join(work, "silent.mp4")
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])
    total = sum(max(1.5, float(l.get("sec") or 3)) for l in short["lines"]) + 2
    bgm = os.path.join(ASSETS, "bgm.mp3")
    if not os.path.exists(bgm):
        bgm = os.path.join(tempfile.gettempdir(), "mcg_bgm.wav")
        if not os.path.exists(bgm):
            make_bgm(bgm, 70)   # 70초짜리를 한 번 만들어 모든 쇼츠가 함께 씀
    _run(["ffmpeg", "-y", "-v", "error", "-i", silent, "-stream_loop", "-1", "-i", bgm,
          "-filter_complex", f"[1:a]volume=0.55,afade=t=out:st={max(0, total - 3)}:d=3[a]",
          "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", out_path])
    return out_path


def main(xlsx, out_dir):
    data = load_script(xlsx)
    pub = dt.date.fromisoformat(data["pub_date"])
    os.makedirs(out_dir, exist_ok=True)
    cache = os.path.join(tempfile.gettempdir(), "mcg_clips")
    src = ClipSource(cache)
    print(f"쇼츠 {len(data['shorts'])}개, 발행일 {pub}, 자료 영상: {src.describe()}")
    outs = []
    for n, short in enumerate(data["shorts"], 1):
        clips = {}
        for line in short["lines"]:
            q = line.get("query")
            if q and q not in clips:
                clips[q] = src.get(q)
        work = tempfile.mkdtemp(prefix=f"short{n}_")
        out = os.path.join(out_dir, f"MCG_Shorts_{pub:%Y%m%d}_{n}.mp4")
        render_short(short, pub, out, clips, work)
        print(f"  쇼츠 {n}: {short['title1']} / {short['title2']} → {out}")
        outs.append(out)
    return outs


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "shorts_out")
