"""Snug bands from 10fps OCR of exactly the frames each segment uses.

For every segment of <Name>/edl.json: extract its frames at 10fps from the source
(same -ss/-frames as the cut), OCR them, cluster Chinese caption lines by centre,
and emit ONE band per caption position, gated to the time that position is on
screen (+-0.15s). Writes <Name>/bands.json (dominant band first per segment).
usage: python3 seg_bands.py Scale8 [...]
"""
import json, os, re, subprocess, sys, concurrent.futures as cf
B = os.path.dirname(os.path.abspath(__file__))
SCAN = "/private/tmp/claude-501/-Users-chien-Edit-Video-Claude/df56e4c8-d49b-44f2-ac7c-4a8fa4ed2e7a/scratchpad/scan"
OCR = f"{SCAN}/ocr"
src = json.load(open(f"{SCAN}/sources.json"))
CJK = re.compile(r"[一-鿿]")
PAD, MIN_H, CAP_H = 20, 120, 64


def seg_ocr(name, i, s):
    d = f"{B}/{name}/segocr/{i:02d}"; os.makedirs(d, exist_ok=True)
    j = f"{d}.jsonl"
    if os.path.exists(j) and os.path.getsize(j) > 0:
        return
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(s["start"]), "-i", src[s["src"]]["path"],
                    "-frames:v", str((s["nf"] + 2) // 3), "-vf", "fps=30,select='not(mod(n\\,3))',scale=540:-2",
                    "-fps_mode", "passthrough", "-q:v", "3", f"{d}/f_%05d.jpg"], check=True)
    with open(j, "w") as fh:
        subprocess.run([OCR, d], stdout=fh, check=True)


DOM = {}


def dominant(sid):
    """the clip's usual caption line position from the whole-clip 2fps scan (None if it has no captions)"""
    if sid in DOM:
        return DOM[sid]
    c = []
    for line in open(f"{SCAN}/ocrjson/{sid}.jsonl"):
        for x, y, w, h, conf, txt in json.loads(line)["t"]:
            if CJK.search(txt) and conf >= 0.5 and 0.45 <= y <= 0.97 and h < 0.07 and abs(x + w / 2 - 0.5) < 0.2:
                c.append((y * 1920, (y + h) * 1920))
    if len(c) < 6:
        DOM[sid] = None; return None
    c.sort(key=lambda b: (b[0] + b[1]) / 2)
    med = (c[len(c) // 2][0] + c[len(c) // 2][1]) / 2
    near = sorted(b for b in c if abs((b[0] + b[1]) / 2 - med) <= 40)
    y0 = sorted(b[0] for b in near)[len(near) // 20]; y1 = sorted(b[1] for b in near)[-1 - len(near) // 20]
    DOM[sid] = (y0, y1); return DOM[sid]


FEED = json.load(open(f"{B}/leak_boxes.json")) if os.path.exists(f"{B}/leak_boxes.json") else {}


def bands_for(name, i, s):
    lines = [(r[2] if len(r) > 2 else s["out"], r[0], r[1]) for r in FEED.get(name, {}).get(str(i), [])]
    for line in open(f"{B}/{name}/segocr/{i:02d}.jsonl"):
        d = json.loads(line); t = s["out"] + (int(d["f"][2:7]) - 1) * 0.1
        for x, y, w, h, c, txt in d["t"]:
            if CJK.search(txt) and len(txt.strip()) >= 1 and 0.40 <= y <= 0.98 and h < 0.08 and w < 0.98:
                lines.append((t, y * 1920, (y + h) * 1920))
    lines.sort(key=lambda r: (r[1] + r[2]) / 2)
    cl = []                                   # cluster by line centre
    for t, y0, y1 in lines:
        c = (y0 + y1) / 2
        if cl and abs(c - cl[-1]["c"]) <= 40:
            k = cl[-1]; k["y0"] = min(k["y0"], y0); k["y1"] = max(k["y1"], y1); k["ts"].append(t)
        else:
            cl.append({"c": c, "y0": y0, "y1": y1, "ts": [t]})
    # merge stacked lines of one 2-line caption (gap <= 30px and on screen together)
    cl.sort(key=lambda k: k["y0"]); m = []
    for k in cl:
        if m and k["y0"] - m[-1]["y1"] <= 30 and set(round(t, 1) for t in k["ts"]) & set(round(t, 1) for t in m[-1]["ts"]):
            m[-1]["y1"] = max(m[-1]["y1"], k["y1"]); m[-1]["ts"] += k["ts"]
        else:
            m.append(k)
    out = []
    end = s["out"] + s["dur"]
    for k in sorted(m, key=lambda k: -len(k["ts"])):
        top, bot = k["y0"] - PAD, k["y1"] + PAD
        if bot - top < MIN_H:
            c = (top + bot) / 2; top, bot = c - MIN_H / 2, c + MIN_H / 2
        top = int(max(0, top)); bot = int(min(1920, bot)); top -= top % 2; bot -= bot % 2
        a = max(s["out"], min(k["ts"]) - 0.3); b = min(end, max(k["ts"]) + 0.3)
        if a - s["out"] < 0.5: a = s["out"]                 # snap to the cut, no band pop-in right after it
        if end - b < 0.5: b = end
        if len(k["ts"]) >= 0.25 * s["nf"] / 3:              # caption on screen for most of the shot -> whole shot
            a, b = s["out"], end
        out.append({"start": round(a, 4), "end": round(b, 4), "top": top, "bottom": bot, "n": len(k["ts"])})
    if not out and dominant(s["src"]):             # OCR saw nothing here, but this clip normally has captions
        y0, y1 = dominant(s["src"])
        top, bot = y0 - PAD, y1 + PAD
        if bot - top < MIN_H:
            c = (top + bot) / 2; top, bot = c - MIN_H / 2, c + MIN_H / 2
        top = int(top) - int(top) % 2; bot = int(bot) - int(bot) % 2
        out.append({"start": round(s["out"], 4), "end": round(end, 4), "top": top, "bottom": bot, "n": 0})
    return out


for name in sys.argv[1:]:
    e = json.load(open(f"{B}/{name}/edl.json")); S = e["segments"]
    with cf.ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda a: seg_ocr(name, *a), enumerate(S)))
    bands = []
    for i, s in enumerate(S):
        bands += bands_for(name, i, s)
    json.dump(bands, open(f"{B}/{name}/bands.json", "w"), indent=1)
    h = [b["bottom"] - b["top"] for b in bands]
    print(f"{name}: {len(bands)} bands over {len(S)} shots, h {min(h)}-{max(h)}, "
          f"shots w/o band {sum(1 for s in S if not any(s['out']<=b['start']<s['out']+s['dur'] for b in bands))}")
