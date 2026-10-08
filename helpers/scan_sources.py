"""Stage 1 - scan every source clip: 2fps frames + Apple Vision OCR + per-frame analysis + clean windows
+ contact sheets for choosing shots by eye.

  cd <videos_dir>/edit/batch
  uv run --project ~/.claude/skills/video-use python ~/.claude/skills/douyin-review-video/helpers/scan_sources.py <videos_dir>
  ... --strips ranges.json    # 2fps verification strips for candidate ranges [[src,a,b],...]

Writes scan/sources.json (sID -> path,dur,w,h), scan/fr/sID/f_00001.jpg (t=(i-1)/2),
scan/ocrjson/sID.jsonl, scan/analysis.json, scan/windows.json, scan/sheet_N.jpg, scan/strip_NN.jpg
"""
import argparse, concurrent.futures as cf, json, os, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import SCAN, ocr_bin

CJK = re.compile(r"[一-鿿]")
# packaging / brand words seen on this product category; extend per product
BRAND = re.compile(r"TONG|YANJ|COLL|TRIP|PEPT|FIRM|MOIST|SERUM|HYAL|PATENT|\d+\s*G\b", re.I)
WATERMARK = re.compile(r"抖音|博主|号[:：]|搬运|@")
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def scan(videos_dir):
    os.makedirs(f"{SCAN}/fr", exist_ok=True); os.makedirs(f"{SCAN}/ocrjson", exist_ok=True)
    files = sorted(f for f in os.listdir(videos_dir) if f.lower().endswith((".mp4", ".mov")) and "(1)" not in f)
    src = {}
    for i, f in enumerate(files):
        p = os.path.abspath(os.path.join(videos_dir, f))
        j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height:format=duration",
                                       "-of", "json", p], capture_output=True, text=True).stdout)
        st = [s for s in j["streams"] if "width" in s][0]
        if st["width"] > st["height"]:
            continue                                   # vertical sources only
        src[f"s{i:02d}"] = {"path": p, "dur": float(j["format"]["duration"]), "w": st["width"], "h": st["height"]}
    json.dump(src, open(f"{SCAN}/sources.json", "w"), ensure_ascii=False, indent=1)
    ocr = ocr_bin()

    def one(k):
        d = f"{SCAN}/fr/{k}"; os.makedirs(d, exist_ok=True)
        if not os.path.exists(d + "/.done"):
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src[k]["path"], "-vf", "fps=2,scale=540:-2",
                            "-q:v", "4", d + "/f_%05d.jpg"], check=True)   # -nostdin: ffmpeg eats a parent loop's stdin
            open(d + "/.done", "w").close()
        o = f"{SCAN}/ocrjson/{k}.jsonl"
        if not (os.path.exists(o) and os.path.getsize(o) > 0):
            with open(o, "w") as fh:
                subprocess.run([ocr, d], stdout=fh, stdin=subprocess.DEVNULL, check=True)
        return k
    with cf.ThreadPoolExecutor(4) as ex:
        for k in ex.map(one, sorted(src)):
            print(k, "scanned", flush=True)
    return src


def analyze(src):
    res = {}
    for k in sorted(src):
        rows = []
        for line in open(f"{SCAN}/ocrjson/{k}.jsonl"):
            d = json.loads(line); t = (int(d["f"][2:7]) - 1) / 2
            boxes = [b for b in d["t"] if b[4] >= 0.3 and len(b[5].strip()) >= 2]
            cap = [b for b in boxes if CJK.search(b[5]) and 0.45 <= b[1] <= 0.97 and abs(b[0] + b[2] / 2 - 0.5) < 0.2 and b[3] < 0.07]
            other = [b[5] for b in boxes if b not in cap and (CJK.search(b[5]) or BRAND.search(b[5]))]
            im = np.asarray(Image.open(f"{SCAN}/fr/{k}/{d['f']}").convert("RGB")).astype(int)
            R, G, Bc = im[..., 0], im[..., 1], im[..., 2]
            orange = float(((R > 190) & (G > 80) & (G < 175) & (Bc < 90) & (R - G > 50)).mean())   # mask on screen
            capb = [min(b[1] for b in cap), max(b[1] + b[3] for b in cap)] if cap else None
            rows.append(dict(t=t, dirty=other, watermark=any(WATERMARK.search(s) for s in other), cap=capb, orange=round(orange, 4)))
        rows.sort(key=lambda r: r["t"]); res[k] = rows
    json.dump(res, open(f"{SCAN}/analysis.json", "w"), ensure_ascii=False)
    wins = []
    for k, rows in res.items():
        if sum(r["watermark"] for r in rows) >= 3:
            print(k, "has a creator watermark -> skipped"); continue
        bad = [bool(r["dirty"]) for r in rows]; n = len(rows)
        unusable = [any(bad[max(0, i - 1):i + 2]) for i in range(n)]     # +-0.5s margin
        i = 0
        while i < n:
            if unusable[i]: i += 1; continue
            j = i
            while j < n and not unusable[j]: j += 1
            t0, t1 = max(rows[i]["t"], 0.2), min(rows[j - 1]["t"] + 0.5, src[k]["dur"] - 0.1)   # skip first 0.2s
            if t1 - t0 >= 2.5:
                o = [rows[q]["orange"] for q in range(i, j)]
                wins.append(dict(src=k, t0=t0, t1=round(t1, 2), dur=round(t1 - t0, 2), omax=round(max(o), 3)))
            i = j
    json.dump(wins, open(f"{SCAN}/windows.json", "w"), indent=0)
    print(len(wins), "clean windows,", round(sum(w["dur"] for w in wins)), "s;", sum(w["omax"] > 0.04 for w in wins), "with the mask on screen")
    return wins


def sheets(wins):
    F = ImageFont.truetype(FONT, 22); TW, TH, per = 150, 267, 24
    for s in range(0, len(wins), per):
        g = Image.new("RGB", (3 * 4 * TW + 20, 8 * TH))
        for n, w in enumerate(wins[s:s + per]):
            r, c = divmod(n, 3); x0, y0 = c * (4 * TW + 10), r * TH
            for q in range(4):
                fi = int((w["t0"] + (w["dur"] - 0.5) * (q + 0.5) / 4) * 2) + 1
                p = f"{SCAN}/fr/{w['src']}/f_{fi:05d}.jpg"
                if os.path.exists(p): g.paste(Image.open(p).resize((TW, TH)), (x0 + q * TW, y0))
            d = ImageDraw.Draw(g); lab = f"#{s + n} {w['src']} {w['t0']:.0f}-{w['t1']:.0f}"
            d.rectangle([x0, y0, x0 + len(lab) * 12, y0 + 26], fill="black"); d.text((x0 + 3, y0 + 2), lab, font=F, fill="yellow")
        g.save(f"{SCAN}/sheet_{s // per}.jpg", quality=85)


def strips(ranges):
    F = ImageFont.truetype(FONT, 16); TW, TH, COLS, per = 90, 160, 20, 12
    rows = []
    for s, a, b in ranges:
        fr = [i for i in range(int(a * 2) + 1, int(b * 2) + 1) if os.path.exists(f"{SCAN}/fr/{s}/f_{i:05d}.jpg")]
        rows += [(s, fr[c:c + COLS]) for c in range(0, len(fr), COLS)]
    for p in range(0, len(rows), per):
        g = Image.new("RGB", (COLS * TW, per * TH)); d = ImageDraw.Draw(g)
        for r, (s, fs) in enumerate(rows[p:p + per]):
            for c, i in enumerate(fs):
                g.paste(Image.open(f"{SCAN}/fr/{s}/f_{i:05d}.jpg").resize((TW, TH)), (c * TW, r * TH))
                if c % 4 == 0:
                    d.rectangle([c * TW, r * TH + TH - 18, c * TW + 50, r * TH + TH], fill="black")
                    d.text((c * TW + 2, r * TH + TH - 18), f"{(i - 1) / 2:.1f}", font=F, fill="white")
            d.rectangle([0, r * TH, 70, r * TH + 18], fill="black"); d.text((2, r * TH), s, font=F, fill="yellow")
        g.save(f"{SCAN}/strip_{p // per:02d}.jpg", quality=85)
    print(len(rows), "strip rows ->", f"{SCAN}/strip_*.jpg")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("videos_dir", nargs="?"); ap.add_argument("--strips")
    a = ap.parse_args()
    if a.strips:
        strips(json.load(open(a.strips)))
    else:
        s = scan(a.videos_dir); sheets(analyze(s))
