"""Karaoke ASS captions from an ElevenLabs Scribe word-level transcript.

Style (approved 2026-10-08): Arial Black 66 @ 1080x1920, UPPERCASE, white text,
black outline 4, the spoken word sweeps to yellow #FFE600 (\\kf). Width-aware
chunking: ~3 words per cue, closes early instead of ever wrapping. The font size
is never shrunk to fit; long words get their own cue instead.

Each cue is centred (\\an5\\pos) inside the cover band active at the cue's start
time (bands.json from detect_captions.py), so the blur strip hugs the caption.
Outside any band, captions sit at --default-cy.

  python karaoke_ass.py "edit/transcripts/<vo>.json" --bands edit/bands.json -o edit/master_karaoke.ass
"""
import argparse, json, re

ap = argparse.ArgumentParser()
ap.add_argument("transcript")
ap.add_argument("--bands", default=None)
ap.add_argument("-o", "--out", default="master_karaoke.ass")
ap.add_argument("--offset", type=float, default=0.0, help="shift if the VO starts later in the output")
ap.add_argument("--font", default="Arial Black")
ap.add_argument("--size", type=int, default=66)
ap.add_argument("--px-per-char", type=int, default=50)   # Arial Black caps @66, conservative
ap.add_argument("--safe-w", type=int, default=940)
ap.add_argument("--words", type=int, default=3)
ap.add_argument("--max-words", type=int, default=4)
ap.add_argument("--default-cy", type=int, default=1455)  # ~76% of frame height
ap.add_argument("--hilite", default="&H0000E6FF")       # ASS BGR: #FFE600
a = ap.parse_args()

WHITE, BLACK = "&H00FFFFFF", "&H00000000"
bands = json.load(open(a.bands)) if a.bands else []


def caption_cy(t):
    for b in bands:
        if b["start"] <= t < b["end"]:
            return (b["top"] + b["bottom"]) // 2
    return a.default_cy


words = [dict(w, start=w["start"] + a.offset, end=w["end"] + a.offset)
         for w in json.load(open(a.transcript))["words"] if w["type"] == "word"]


def width(ws):
    return len(" ".join(w["text"] for w in ws)) * a.px_per_char


cues, cur = [], []
for i, w in enumerate(words):
    if cur and (width(cur + [w]) > a.safe_w or len(cur) >= a.max_words):
        cues.append(cur); cur = []
    cur.append(w)
    nxt = words[i + 1] if i + 1 < len(words) else None
    gap = (nxt["start"] - w["end"]) if nxt else 9
    if len(cur) >= a.words or w["text"][-1] in ".,!?" or gap >= 0.3:
        cues.append(cur); cur = []
if cur:
    cues.append(cur)


def ts(t):
    cs = int(round(t * 100)); h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


lines = []
for ci, cue in enumerate(cues):
    start = cue[0]["start"]
    nxt_start = cues[ci + 1][0]["start"] if ci + 1 < len(cues) else None
    end = cue[-1]["end"] + 0.15
    if nxt_start is not None:
        if nxt_start - cue[-1]["end"] < 0.35:
            end = nxt_start                     # hold through short gaps: no flicker
        end = min(end, nxt_start)
    parts = []
    for wi, w in enumerate(cue):
        w_end = cue[wi + 1]["start"] if wi + 1 < len(cue) else w["end"]
        k = max(1, int(round((w_end - w["start"]) * 100)))
        parts.append(f"{{\\kf{k}}}" + re.sub(r"[.,!?]+$", "", w["text"]).upper())
    body = f"{{\\an5\\pos(540,{caption_cy(start)})\\fad(60,0)}}" + " ".join(parts)
    lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Kara,,0,0,0,,{body}")

# PrimaryColour = sung (highlight), SecondaryColour = not yet sung (white)
header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Kara,{a.font},{a.size},{a.hilite},{WHITE},{BLACK},&H80000000,0,0,0,0,100,100,0,0,1,4,1,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
open(a.out, "w").write(header + "\n".join(lines) + "\n")
print(f"{len(cues)} cues -> {a.out}")
