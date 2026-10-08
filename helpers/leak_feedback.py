"""render OCR (out10) -> leak boxes per segment -> leak_boxes.json (accumulates)"""
import json, re, os, sys
W = "/private/tmp/claude-501/-Users-chien-Edit-Video-Claude/df56e4c8-d49b-44f2-ac7c-4a8fa4ed2e7a/scratchpad/scan"
CJK = re.compile(r"[一-鿿]")
fb = json.load(open("leak_boxes.json")) if os.path.exists("leak_boxes.json") else {}
total = 0
for f in sys.argv[1:]:
    S = json.load(open(f"{f}/edl.json"))["segments"]; bands = json.load(open(f"{f}/bands.json"))
    for line in open(f"{W}/out10/{f}.jsonl"):
        d = json.loads(line); t = (int(d["f"][2:7]) - 1) / 10
        i = next((i for i, s in enumerate(S) if s["out"] <= t < s["out"] + s["dur"]), None)
        if i is None: continue
        for x, y, w, h, c, txt in d["t"]:
            y0, y1 = y * 1920, (y + h) * 1920
            if not CJK.search(txt) or y < 0.4 or h > 0.08 or c < 0.5: continue
            if any(b["start"] <= t < b["end"] and b["top"] <= y0 + 4 and y1 - 4 <= b["bottom"] for b in bands): continue
            fb.setdefault(f, {}).setdefault(str(i), []).append([int(y0), int(y1), t]); total += 1
            print(f, "seg", i, S[i]["src"], f"t={t:.1f}", int(y0), int(y1), round(c, 1), txt[:12])
json.dump(fb, open("leak_boxes.json", "w"), indent=1)
print("new leak boxes:", total)
