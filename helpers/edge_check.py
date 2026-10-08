"""Zero-leak check: look for caption-like pixels just OUTSIDE each cover band.

Scans --margin px above and below every band in bands.json at --fps on the
UNBANDED base video, and prints every frame where text-like pixels appear.
Each hit must be eyeballed (crop that frame): real caption -> widen that band;
hair / clothing / props -> ignore.

  uv run --project <video-use> python edge_check.py edit/base_video.mp4 edit/bands.json
"""
import argparse, json, subprocess
import numpy as np

FF = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"


def dilate(m, r=3):
    o = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            o |= np.roll(np.roll(m, dy, 0), dx, 1)
    return o


ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("bands")
ap.add_argument("--fps", type=float, default=4)
ap.add_argument("--margin", type=int, default=80)
a = ap.parse_args()

hits = 0
for b in json.load(open(a.bands)):
    t0, t1, top, bot = b["start"], b["end"], b["top"], b["bottom"]
    n = int((t1 - t0) * a.fps)
    raw = subprocess.run([FF, "-v", "error", "-ss", str(t0), "-i", a.video, "-frames:v", str(n),
                          "-vf", f"fps={a.fps}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, 1920, 1080, 3).astype(np.int16)
    for i, f in enumerate(fr):
        R, G, B = f[..., 0], f[..., 1], f[..., 2]
        txt = (((R > 205) & (G > 205) & (B > 205)) | ((R > 200) & (G > 165) & (B < 110))) \
            & dilate(np.maximum(np.maximum(R, G), B) < 70)
        txt[:, :40] = False; txt[:, -40:] = False
        # wide strips catch whole caption lines outside the band; thin 12px strips
        # (low threshold) catch a glyph that is sliced by the band edge
        for name, y0, y1, thr in (("above", max(0, top - a.margin), top, 40),
                                  ("below", bot, min(1920, bot + a.margin), 40),
                                  ("cut-top", max(0, top - 12), top, 8),
                                  ("cut-bottom", bot, min(1920, bot + 12), 8)):
            cnt = int(txt[y0:y1].sum())
            if cnt > thr:
                rows = np.where(txt[y0:y1].sum(1) > 0)[0]
                hits += 1
                print(f"t={t0 + i / a.fps:7.2f} {name} band {top}-{bot}: {cnt}px at rows "
                      f"{y0 + rows.min()}-{y0 + rows.max()}  -> eyeball this frame")
print(f"done, {hits} candidate(s)")
