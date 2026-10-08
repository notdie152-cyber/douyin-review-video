"""Final composite: snug blur bands over old captions -> karaoke ASS -> mux audio.

One crop->boxblur->overlay chain per band, each gated to its own time range
(segment-gated, not cue-gated: no gaps where old text could flash through).
No darkening: approved look is blur + desaturate only ("mọi thứ rất tối" was
the rejection of the earlier eq=brightness=-0.18 band).

  python render_snug.py edit/base_video.mp4 edit/bands.json edit/master_karaoke.ass \
      --audio edit/mix.m4a -o edit/final.mp4
"""
import argparse, json, os, subprocess

FF = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"   # plain brew ffmpeg has no libass
FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts")

ap = argparse.ArgumentParser()
ap.add_argument("base")
ap.add_argument("bands")
ap.add_argument("ass")
ap.add_argument("--audio", required=True, help="file whose first audio stream is the final mix")
ap.add_argument("--blur", default="22:2")
ap.add_argument("--saturation", type=float, default=0.55)
ap.add_argument("-o", "--out", required=True)
a = ap.parse_args()

bands = json.load(open(a.bands))
n = len(bands)
fc = f"[0:v]split={n + 1}[base]" + "".join(f"[s{i}]" for i in range(n)) + ";"
prev = "base"
for i, b in enumerate(bands):
    h = b["bottom"] - b["top"]
    lr, lp = (int(v) for v in a.blur.split(":"))
    lr = min(lr, h // 4 - 1)          # boxblur limit: chroma radius < h/4 (yuv420) -- thin bands need less
    fc += (f"[s{i}]crop=1080:{h}:0:{b['top']},boxblur={lr}:{lp},eq=saturation={a.saturation}[bl{i}];"
           f"[{prev}][bl{i}]overlay=0:{b['top']}:enable='between(t,{b['start']},{b['end']})'[v{i}];")
    prev = f"v{i}"
fc += f"[{prev}]ass=filename='{a.ass}':fontsdir='{os.path.normpath(FONTS)}'[out]"   # subtitles LAST (video-use Hard Rule 1)

subprocess.run([FF, "-v", "error", "-y", "-i", a.base, "-i", a.audio, "-filter_complex", fc,
                "-map", "[out]", "-map", "1:a:0", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
                "-movflags", "+faststart", a.out], check=True)
print("wrote", a.out)
