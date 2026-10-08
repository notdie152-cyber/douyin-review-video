"""Stage 6 - verify renders: OCR <out>/<Name>.mp4 at 10fps and list Chinese text that is NOT under a band.
Hits with confidence >= 0.5 are appended (with their time) to leak_boxes.json, so
`seg_bands.py <Name> && build_batch.py <Name> --finish` covers them. Repeat until it prints 0.
Low-confidence hits are listed only: eyeball them (shirt prints, our own caption merged with background).

  python3 verify_leaks.py Scale8 [...]    (cwd = batch dir)
"""
import json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import B, ocr_bin, plan

CJK = re.compile(r"[一-鿿]")
OUT = os.path.abspath(os.path.join(B, plan().get("_out", "output")))
fb = json.load(open(f"{B}/leak_boxes.json")) if os.path.exists(f"{B}/leak_boxes.json") else {}
new = 0
for f in sys.argv[1:]:
    d = f"{B}/{f}/render10"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", f"{OUT}/{f}.mp4", "-vf", "fps=10,scale=720:-2",
                    "-q:v", "3", f"{d}/f_%05d.jpg"], check=True)
    ocr = subprocess.run([ocr_bin(), d], capture_output=True, text=True, check=True).stdout
    S = json.load(open(f"{B}/{f}/edl.json"))["segments"]; bands = json.load(open(f"{B}/{f}/bands.json"))
    for line in ocr.splitlines():
        r = json.loads(line); t = (int(r["f"][2:7]) - 1) / 10
        i = next((i for i, s in enumerate(S) if s["out"] <= t < s["out"] + s["dur"]), None)
        if i is None: continue
        for x, y, w, h, c, txt in r["t"]:
            y0, y1 = y * 1920, (y + h) * 1920
            if not CJK.search(txt) or y < 0.4 or h > 0.08: continue
            if any(b["start"] <= t < b["end"] and b["top"] <= y0 + 4 and y1 - 4 <= b["bottom"] for b in bands): continue
            tag = "LEAK" if c >= 0.5 else "check"
            print(f"{f} {tag} t={t:.1f} shot {i} ({S[i]['src']}) y={int(y0)}-{int(y1)} conf={c:.1f} {txt[:14]}  -> {d}/{r['f']}")
            if c >= 0.5:
                fb.setdefault(f, {}).setdefault(str(i), []).append([int(y0), int(y1), t]); new += 1
json.dump(fb, open(f"{B}/leak_boxes.json", "w"), indent=1)
print("new leaks fed back:", new)
