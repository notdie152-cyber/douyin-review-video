"""Batch-build Scale8..Scale13 from plan.json + VO transcripts.

usage: uv run --project ~/.claude/skills/video-use python build_batch.py Scale8 [Scale9 ...] [--edl-only]
"""
import difflib, json, os, re, subprocess, sys

B = os.path.dirname(os.path.abspath(__file__))
SCAN = "/private/tmp/claude-501/-Users-chien-Edit-Video-Claude/df56e4c8-d49b-44f2-ac7c-4a8fa4ed2e7a/scratchpad/scan"
SKILL = os.path.expanduser("~/.claude/skills/douyin-review-video/helpers")
FF = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
MUSIC = os.path.join(B, "..", "assets", "bg_music.mp3")
OUT = os.path.abspath(os.path.join(B, "..", "..", "output"))
SCRIPT_OF = {"Scale8": 1, "Scale9": 2, "Scale10": 3, "Scale11": 4, "Scale12": 5, "Scale13": 6}
MAX_SHOT, MIN_SHOT, TAIL = 3.8, 1.2, 1.0
SPARES = {
    "Scale8": [["s40", 12.0, 15.5], ["s45", 13.0, 19.0], ["s13", 24.0, 26.0]],
    "Scale9": [["s56", 9.0, 19.0], ["s35", 6.5, 10.5], ["s20", 3.0, 9.0]],
    "Scale10": [["s15", 28.5, 33.0], ["s29", 41.0, 45.0]],
    "Scale11": [["s44", 0.2, 0.0]],
    "Scale12": [["s21", 27.0, 30.0], ["s54", 35.5, 37.5]],
    "Scale13": [["s32", 38.5, 39.5]],
}

src = json.load(open(f"{SCAN}/sources.json"))
ana = json.load(open(f"{SCAN}/analysis.json"))
plan = json.load(open(f"{B}/plan.json"))


def run(cmd):
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout)


def toks(s):
    return [t for t in re.split(r"[^a-z0-9']+", s.lower().replace("’", "'")) if t]


def line_spans(n):
    lines = [l for l in open(f"{B}/vo/s{n}.txt").read().splitlines() if l.strip()]
    words = [w for w in json.load(open(f"{B}/transcripts/vo{n}.json"))["words"] if w["type"] == "word"]
    st, lid = [], []
    for i, l in enumerate(lines):
        t = toks(l); st += t; lid += [i] * len(t)
    wt, widx = [], []
    for j, w in enumerate(words):
        t = toks(w["text"]); wt += t; widx += [j] * len(t)
    m = difflib.SequenceMatcher(a=st, b=wt, autojunk=False)
    s2w = {}
    for a, b, size in m.get_matching_blocks():
        for k in range(size):
            s2w[a + k] = widx[b + k]
    starts = []
    for i in range(len(lines)):
        first = lid.index(i)
        k = next(k for k in range(first, len(st)) if k in s2w)
        starts.append(words[s2w[k]]["start"])
    starts[0] = 0.0
    total = dur(f"{B}/vo/vo{n}.mp3") + TAIL
    bounds = [max(0.0, s - 0.05) if i else 0.0 for i, s in enumerate(starts)] + [total]
    return [(bounds[i], bounds[i + 1]) for i in range(len(lines))], total


def build_edl(name):
    n = SCRIPT_OF[name]
    spans, total = line_spans(n)
    lines = plan[name]
    assert len(lines) == len(spans), (name, len(lines), len(spans))
    used = {}            # (src,a,b) -> consumed seconds
    spare = [tuple(r) for r in SPARES[name]]
    segs, t = [], 0.0

    def remaining(r):              # never read past the end of the source file
        return min(r[2], src[r[0]]["dur"] - 0.1) - r[1] - used.get(r, 0.0)

    for li, (a, b) in enumerate(spans):
        need = b - t
        ranges = [tuple(r) for r in lines[li]]
        k = 0
        while need > 0.05:
            pool = [r for r in ranges if remaining(r) >= 0.9] or [r for r in spare if remaining(r) >= 0.9]
            if not pool:
                raise SystemExit(f"{name}: out of footage at line {li}, need {need:.1f}s")
            r = pool[k % len(pool)]; k += 1
            rem = remaining(r)
            if need <= MAX_SHOT + 0.5 and rem >= need:
                L = need                                   # finish the line in one shot
            else:
                L = min(MAX_SHOT, rem)
                if need - L < MIN_SHOT:                    # never leave a flash-length tail
                    L = need - MIN_SHOT
                if L < MIN_SHOT:
                    L = min(rem, need)
            s0 = r[1] + used.get(r, 0.0)
            segs.append({"src": r[0], "start": round(s0, 3), "dur": round(L, 3), "line": li, "r0": r[1], "r1": r[2]})
            used[r] = used.get(r, 0.0) + L
            need -= L; t += L
    # absorb flash-length slivers (<0.8s) into a neighbour that still has footage left in its range
    i = 0
    while i < len(segs):
        x = segs[i]
        if x["dur"] < 0.8 and len(segs) > 1:
            p_ = segs[i - 1] if i > 0 else None
            n_ = segs[i + 1] if i + 1 < len(segs) else None
            if p_ and p_["start"] + p_["dur"] + x["dur"] <= p_["r1"] + 1e-6:
                p_["dur"] = round(p_["dur"] + x["dur"], 3); segs.pop(i); continue
            if n_ and n_["start"] - x["dur"] >= n_["r0"] - 1e-6:
                n_["start"] = round(n_["start"] - x["dur"], 3); n_["dur"] = round(n_["dur"] + x["dur"], 3); segs.pop(i); continue
            if n_ and n_["start"] + n_["dur"] + x["dur"] <= n_["r1"] + 1e-6:
                n_["dur"] = round(n_["dur"] + x["dur"], 3); segs.pop(i); continue
            d = 1.0 - x["dur"]
            if n_ and x["start"] + 1.0 <= x["r1"] + 1e-6 and n_["dur"] - d >= 1.0:
                x["dur"] = 1.0; n_["start"] = round(n_["start"] + d, 3); n_["dur"] = round(n_["dur"] - d, 3); i += 1; continue
            if p_ and p_["start"] - x["dur"] >= p_["r0"] - 1e-6:
                p_["start"] = round(p_["start"] - x["dur"], 3); p_["dur"] = round(p_["dur"] + x["dur"], 3); segs.pop(i); continue
        i += 1
    return segs, total


CJK = re.compile(r"[\u4e00-\u9fff]")
RAW = {}
EXTRA = json.load(open(f"{B}/extra_caps.json")) if os.path.exists(f"{B}/extra_caps.json") else {}


def raw_caps(sid):
    """per-frame caption line boxes (y0,y1 in px) from the OCR dump, caption-zone lines only"""
    if sid not in RAW:
        out = {}
        for line in open(f"{SCAN}/ocrjson/{sid}.jsonl"):
            d = json.loads(line); t = (int(d["f"][2:7]) - 1) / 2
            bx = []
            for x, y, w, h, c, txt in d["t"]:
                if c >= 0.3 and len(txt.strip()) >= 2 and CJK.search(txt) and 0.45 <= y <= 0.97 \
                        and abs(x + w / 2 - 0.5) < 0.2 and h < 0.07:
                    bx.append((y * 1920, (y + h) * 1920))
            out[t] = bx
        RAW[sid] = out
    return RAW[sid]


def caption_clusters(sid, a, b):
    """y-clusters of caption lines seen in frames inside [a,b] (+-0.25s)"""
    boxes = [bx for t, f in raw_caps(sid).items() if a - 1.5 <= t <= b + 1.5 for bx in f]
    # caption boxes the 2fps source scan missed, found by the 10fps OCR of a previous render
    boxes += [(y0, y1) for t, y0, y1 in EXTRA.get(sid, []) if a - 1.5 <= t <= b + 1.5]
    boxes.sort(key=lambda bx: (bx[0] + bx[1]) / 2)
    cl = []                       # group by line centre (+-70px) so different caption heights never chain together
    for y0, y1 in boxes:
        c = (y0 + y1) / 2
        if cl and abs(c - cl[-1][2]) <= 70:
            cl[-1][0] = min(cl[-1][0], y0); cl[-1][1] = max(cl[-1][1], y1)
        else:
            cl.append([y0, y1, c])
    cl = [[a_, b_] for a_, b_, _ in cl]
    return cl


def build(name, edl_only=False):
    segs, total = build_edl(name)
    wd = f"{B}/{name}"; os.makedirs(f"{wd}/clips", exist_ok=True)
    t = 0.0
    for s in segs:                       # whole frames @30fps so planned cut times == real cut times (no drift)
        s["nf"] = max(1, round(s["dur"] * 30)); s["dur"] = s["nf"] / 30
        s["out"] = t; t += s["dur"]
        s["cap"] = caption_clusters(s["src"], s["start"], s["start"] + s["dur"])
    caps = [(c[0] + c[1]) / 2 for s in segs for c in s["cap"]]
    cy = int(min(1560, max(1300, sorted(caps)[len(caps) // 2]))) if caps else 1455
    bands = []
    for s in segs:
        for y0, y1 in s["cap"]:
            if y0 - 140 <= cy <= y1 + 140:            # our caption sits near this line: one shared strip
                y0, y1 = min(y0, cy - 48), max(y1, cy + 48)
            top = int(y0 - 22); bot = int(y1 + 22)
            top -= top % 2; bot += bot % 2
            bands.append({"start": round(s["out"], 4), "end": round(s["out"] + s["dur"], 4), "top": max(0, top), "bottom": min(1920, bot)})
    json.dump({"segments": segs, "total": total, "caption_cy": cy}, open(f"{wd}/edl.json", "w"), indent=1)
    json.dump(bands, open(f"{wd}/bands.json", "w"), indent=1)
    print(f"{name}: {len(segs)} shots, {len({s['src'] for s in segs})} sources, {t:.2f}s (VO+tail {total:.2f}), caption cy={cy}, {len(bands)} bands")
    if edl_only:
        return
    # 1) per-segment extract, scaled to 1080x1920@30, no audio
    lst = []
    for i, s in enumerate(segs):
        p = f"{wd}/clips/c{i:02d}.mp4"
        run([FF, "-v", "error", "-y", "-ss", str(s["start"]), "-i", src[s["src"]]["path"], "-frames:v", str(s["nf"]),
             "-vf", "fps=30,scale=1080:1920:flags=lanczos,setsar=1", "-an", "-c:v", "libx264", "-crf", "18",
             "-preset", "fast", "-pix_fmt", "yuv420p", p])
        lst.append(f"file '{p}'")
    open(f"{wd}/concat.txt", "w").write("\n".join(lst) + "\n")
    run([FF, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{wd}/concat.txt", "-c", "copy", f"{wd}/base.mp4"])
    # 2) audio: VO + music ducked under VO, two-pass loudnorm to -14 LUFS / -1 dBTP
    n = SCRIPT_OF[name]
    fc = (f"[0:a]aresample=48000,apad=whole_dur={total},asplit[v1][v2];"
          f"[1:a]aresample=48000,atrim=0:{total},volume=0.30,afade=t=out:st={total-1.5}:d=1.5[m];"
          f"[m][v1]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[md];"
          f"[v2][md]amix=inputs=2:normalize=0:duration=first[out]")
    run([FF, "-v", "error", "-y", "-i", f"{B}/vo/vo{n}.mp3", "-i", MUSIC, "-filter_complex", fc, "-map", "[out]",
         "-ar", "48000", f"{wd}/mix_raw.wav"])
    meas = subprocess.run([FF, "-hide_banner", "-i", f"{wd}/mix_raw.wav", "-af",
                           "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True, stdin=subprocess.DEVNULL).stderr
    j = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
    run([FF, "-v", "error", "-y", "-i", f"{wd}/mix_raw.wav", "-af",
         f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
         f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true",
         "-ar", "48000", f"{wd}/mix.wav"])
    # 3) karaoke captions at a fixed height for the whole video, 4) final render
    run(["python3", f"{SKILL}/karaoke_ass.py", f"{B}/transcripts/vo{n}.json", "--default-cy", str(cy),
         "-o", f"{wd}/karaoke.ass"])
    os.makedirs(OUT, exist_ok=True)
    run(["python3", f"{SKILL}/render_snug.py", f"{wd}/base.mp4", f"{wd}/bands.json", f"{wd}/karaoke.ass",
         "--audio", f"{wd}/mix.wav", "-o", f"{OUT}/{name}.mp4"])


if __name__ == "__main__":
    edl_only = "--edl-only" in sys.argv
    for name in [a for a in sys.argv[1:] if not a.startswith("--")]:
        build(name, edl_only)
