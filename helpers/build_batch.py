"""Stage 3 (cut) and stage 5 (finish) of the batch pipeline. Run with cwd = the batch dir.

  build_batch.py Scale8 Scale9 --plan-only   # line-aligned shot plan -> <Name>/edl.json, print stats
  build_batch.py Scale8 Scale9               # + cut clips (whole frames), base.mp4, VO+music mix.wav
  build_batch.py Scale8 Scale9 --finish      # karaoke.ass centred in <Name>/bands.json (seg_bands.py) + final render

plan.json:
  {"_videos": {"Scale8": {"script": 1, "spares": [["s40",12.0,15.5]]}, ...},
   "_music": "../assets/bg_music.mp3" | null,  "_out": "../../output",
   "Scale8": [ [[src,a,b], ...],   <- one list of clean ranges per script line (sentence), in order
               ... ], ...}
"""
import difflib, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import B, FF, HELPERS, dur, plan, run, sources

MAX_SHOT, MIN_SHOT, TAIL = 3.8, 1.2, 1.0
P = plan(); CFG = P["_videos"]; src = sources()
OUT = os.path.abspath(os.path.join(B, P.get("_out", "output")))
MUSIC = os.path.abspath(os.path.join(B, P["_music"])) if P.get("_music") else None


def toks(s):
    return [t for t in re.split(r"[^a-z0-9']+", s.lower().replace("’", "'")) if t]


def line_spans(n):
    lines = [l for l in open(f"{B}/scripts/s{n}.txt").read().splitlines() if l.strip()]
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
    n = CFG[name]["script"]
    spans, total = line_spans(n)
    lines = P[name]
    assert len(lines) == len(spans), (name, len(lines), len(spans))
    used = {}            # (src,a,b) -> consumed seconds
    spare = [tuple(r) for r in CFG[name].get("spares", [])]
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


def cut(name):
    segs, total = build_edl(name)
    wd = f"{B}/{name}"; os.makedirs(f"{wd}/clips", exist_ok=True)
    t = 0.0
    for s in segs:                       # whole frames @30fps so planned cut times == real cut times (no drift)
        s["nf"] = max(1, round(s["dur"] * 30)); s["dur"] = s["nf"] / 30
        s["out"] = t; t += s["dur"]
    json.dump({"segments": segs, "total": total}, open(f"{wd}/edl.json", "w"), indent=1)
    print(f"{name}: {len(segs)} shots from {len({s['src'] for s in segs})} clips, {t:.2f}s (VO+tail {total:.2f}), "
          f"shot {min(s['dur'] for s in segs):.2f}-{max(s['dur'] for s in segs):.2f}s")
    return segs, total, wd


def build(name):
    segs, total, wd = cut(name)
    lst = []
    for i, s in enumerate(segs):
        p = f"{wd}/clips/c{i:02d}.mp4"
        run([FF, "-v", "error", "-y", "-ss", str(s["start"]), "-i", src[s["src"]]["path"], "-frames:v", str(s["nf"]),
             "-vf", "fps=30,scale=1080:1920:flags=lanczos,setsar=1", "-an", "-c:v", "libx264", "-crf", "18",
             "-preset", "fast", "-pix_fmt", "yuv420p", p])
        got = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v", "-show_entries",
                                  "stream=nb_read_frames", "-of", "csv=p=0", p], capture_output=True, text=True).stdout)
        if got != s["nf"]:
            raise SystemExit(f"{name} clip {i}: {got} frames, planned {s['nf']} - every later cut would drift")
        lst.append(f"file '{p}'")
    open(f"{wd}/concat.txt", "w").write("\n".join(lst) + "\n")
    run([FF, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{wd}/concat.txt", "-c", "copy", f"{wd}/base.mp4"])
    n = CFG[name]["script"]; vo = f"{B}/vo/vo{n}.mp3"
    if MUSIC:   # music ducked under the VO
        fc = (f"[0:a]aresample=48000,apad=whole_dur={total},asplit[v1][v2];"
              f"[1:a]aresample=48000,atrim=0:{total},volume=0.30,afade=t=out:st={total-1.5}:d=1.5[m];"
              f"[m][v1]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[md];"
              f"[v2][md]amix=inputs=2:normalize=0:duration=first[out]")
        run([FF, "-v", "error", "-y", "-i", vo, "-stream_loop", "-1", "-i", MUSIC, "-filter_complex", fc, "-map", "[out]",
             "-ar", "48000", f"{wd}/mix_raw.wav"])
    else:
        run([FF, "-v", "error", "-y", "-i", vo, "-af", f"aresample=48000,apad=whole_dur={total}", f"{wd}/mix_raw.wav"])
    meas = subprocess.run([FF, "-hide_banner", "-i", f"{wd}/mix_raw.wav", "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json",
                           "-f", "null", "-"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stderr
    j = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
    run([FF, "-v", "error", "-y", "-i", f"{wd}/mix_raw.wav", "-af",
         f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
         f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true",
         "-ar", "48000", f"{wd}/mix.wav"])
    print(f"{name}: base.mp4 + mix.wav ready -> run seg_bands.py, then --finish")


def finish(name):
    wd = f"{B}/{name}"; n = CFG[name]["script"]
    bands = json.load(open(f"{wd}/bands.json"))
    cs = sorted((b["top"] + b["bottom"]) // 2 for b in bands)
    cy = cs[len(cs) // 2] if cs else 1455           # where captions sit in shots without a band
    run(["python3", f"{HELPERS}/karaoke_ass.py", f"{B}/transcripts/vo{n}.json", "--bands", f"{wd}/bands.json",
         "--default-cy", str(cy), "-o", f"{wd}/karaoke.ass"])
    os.makedirs(OUT, exist_ok=True)
    run(["python3", f"{HELPERS}/render_snug.py", f"{wd}/base.mp4", f"{wd}/bands.json", f"{wd}/karaoke.ass",
         "--audio", f"{wd}/mix.wav", "-o", f"{OUT}/{name}.mp4"])


if __name__ == "__main__":
    names = [a for a in sys.argv[1:] if not a.startswith("--")]
    for name in names:
        if "--plan-only" in sys.argv: cut(name)
        elif "--finish" in sys.argv: finish(name)
        else: build(name)
