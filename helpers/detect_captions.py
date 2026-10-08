"""Measure where burned-in captions sit, per cut segment, and propose snug cover bands.

Caption pixel = bright white or yellow pixel with a dark outline pixel within 2px
(burned-in Douyin/TikTok captions always carry a dark stroke). Rows with enough of
them form the caption line(s). For each segment, the band is the union of every
detected caption extent in that segment plus --pad px. Segments with no detections
get no band (leave the footage untouched there).

Usage (run with the video-use env, it has numpy):
  uv run --project <video-use> python detect_captions.py edit/base_video.mp4 \
      --segments 0,2.5,5.4,16.833,27.833,...,72.6 --merge 0-3,3-4,4-6 -o edit/bands.json

--segments : cut boundaries on the output timeline (from the EDL / clip durations)
--merge    : optional groups of segment indexes that come from the SAME source clip
             and should share one band (e.g. "0-3" = segments 0,1,2). Default: one
             band per segment.

Known blind spot: a lone character on a 2nd caption line (e.g. "了") has too few
pixels per row to register. Always follow up with edge_check.py.
"""
import argparse, json, subprocess
import numpy as np

FF = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
AW, AH = 540, 960            # analysis scale; results are reported at 1080x1920


def frames(src, t0, t1, fps):
    n = max(1, int((t1 - t0) * fps))
    cmd = [FF, "-v", "error", "-ss", f"{t0:.3f}", "-i", src, "-frames:v", str(n),
           "-vf", f"fps={fps},scale={AW}:{AH}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    arr = np.frombuffer(raw, np.uint8).reshape(-1, AH, AW, 3).astype(np.int16)
    for i, f in enumerate(arr):
        yield t0 + i / fps, f


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def caption_rows(f, y_min_frac):
    R, G, B = f[..., 0], f[..., 1], f[..., 2]
    white = (R > 205) & (G > 205) & (B > 205)
    yellow = (R > 200) & (G > 165) & (B < 110)
    dark = np.maximum(np.maximum(R, G), B) < 70
    text = (white | yellow) & dilate(dark, 2)
    text[: int(AH * y_min_frac)] = False
    text[:, : int(AW * 0.04)] = False
    text[:, int(AW * 0.96):] = False
    rows = text.sum(1)
    hit = np.where(rows >= 5)[0]
    if len(hit) == 0:
        return None
    clusters, cur = [], [hit[0]]
    for y in hit[1:]:
        if y - cur[-1] <= 6:
            cur.append(y)
        else:
            clusters.append(cur); cur = [y]
    clusters.append(cur)
    merged = [clusters[0]]
    for c in clusters[1:]:
        if c[0] - merged[-1][-1] <= 14:          # 2-line captions
            merged[-1] = merged[-1] + c
        else:
            merged.append(c)
    best = max(merged, key=lambda c: rows[c[0]:c[-1] + 1].sum())
    if best[-1] - best[0] < 6 or rows[best[0]:best[-1] + 1].sum() < 120:
        return None
    top, bot = int(best[0]), int(best[-1])
    # a 2nd line holding a single glyph (e.g. "了") is too sparse for the row
    # threshold above: grow the line into any weak text rows right next to it
    weak = rows >= 1
    for step, edge in ((1, "bot"), (-1, "top")):
        y, gap = (bot if edge == "bot" else top) + step, 0
        while 0 <= y < AH and gap <= 10:
            if weak[y]:
                if edge == "bot": bot = y
                else: top = y
                gap = 0
            else:
                gap += 1
            y += step
    return top * 2, bot * 2 + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--segments", required=True)
    ap.add_argument("--merge", default="")
    ap.add_argument("--fps", type=float, default=4)
    ap.add_argument("--pad", type=int, default=22)
    ap.add_argument("--y-min", type=float, default=0.45, help="ignore text above this frame fraction")
    ap.add_argument("--tolerance", type=int, default=90, help="px from median caption centre still counted")
    ap.add_argument("--min-hits", type=int, default=3, help="detections needed before a segment gets a band")
    ap.add_argument("-o", "--out", default="bands.json")
    a = ap.parse_args()

    bounds = [float(x) for x in a.segments.split(",")]
    segs = list(zip(bounds[:-1], bounds[1:]))
    groups = []
    if a.merge:
        for g in a.merge.split(","):
            i, j = (int(x) for x in g.split("-"))
            groups.append(list(range(i, j)))
    covered = {i for g in groups for i in g}
    groups += [[i] for i in range(len(segs)) if i not in covered]
    groups.sort()

    bands = []
    for g in groups:
        t0, t1 = segs[g[0]][0], segs[g[-1]][1]
        hits = [r for _, f in frames(a.video, t0, t1, a.fps) if (r := caption_rows(f, a.y_min))]
        line = f"{t0:7.2f}-{t1:7.2f}  {len(hits):3d} hits"
        if len(hits) < a.min_hits:
            print(line, " -> no band")
            continue
        # one stray bright object (inset photo, logo, pouch) must not stretch the band:
        # keep only detections whose centre is near the median caption centre
        med = float(np.median([(h[0] + h[1]) / 2 for h in hits]))
        keep = [h for h in hits if abs((h[0] + h[1]) / 2 - med) <= a.tolerance]
        if len(keep) < len(hits):
            line += f" ({len(hits) - len(keep)} outlier(s) dropped)"
        top = max(0, min(h[0] for h in keep) - a.pad)
        bot = min(1920, max(h[1] for h in keep) + a.pad)
        bot += (bot - top) % 2                       # even height for yuv420
        bands.append({"start": round(t0, 3), "end": round(t1, 3), "top": top, "bottom": bot})
        print(line, f" -> band y{top}-{bot} ({top/19.2:.1f}%-{bot/19.2:.1f}%)")
    json.dump(bands, open(a.out, "w"), indent=1)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
