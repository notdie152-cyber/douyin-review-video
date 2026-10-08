---
name: douyin-review-video
description: Turn a folder of scraped Douyin/TikTok product clips (Chinese captions, Chinese packaging) plus an English script or voiceover into a high-converting English product-review ad for dropshipping. Cuts highlight shots, drops any shot showing Chinese packaging/brand text, mutes source audio, uses or generates an English voiceover, covers burned-in Chinese captions with snug blur bands, and burns karaoke captions (white text, black outline, yellow word sweep). Use with the video-use skill. Triggers: "video review sản phẩm", "video chuyển đổi cao", "xóa phụ đề tiếng Trung", "phụ đề karaoke", "voice over tiếng Anh", "dropship ad from Douyin clips", "editvideoskill".
---

# Douyin → English product-review ad

This was approved on 2026-10-08 on a real ad (jawline lift mask). Apply these values directly. Don't re-ask about them, and deviate only when the creator asks for something different for a specific video.

**Depends on [video-use](https://github.com/browser-use/video-use).** That skill provides Scribe transcription (`helpers/transcribe.py`), the Hard Rules (subtitles last, 30ms fades, never cut inside a word), the `edit/` layout, and `project.md` memory. Read `video-use/SKILL.md` first, then this file. Helpers referenced as `helpers/...` below live in **this** skill's folder.

## The brief, in the creator's words → what it means

| Ask | Do |
|---|---|
| cắt những cảnh highlight của sản phẩm | Pick shots of the product in use: applying, stretching the fabric, wrapping the jaw, hands lifting the face, a before→after reveal. Match one shot group to each script beat. |
| loại bỏ phụ đề tiếng Trung | Snug blur strip over the old captions (below). The creator's tolerance for any legible Chinese is zero. |
| loại bỏ đoạn show sản phẩm hiển thị rõ chữ Trung | Never use a frame that shows the box, sachet, pamphlet, or brand name (e.g. TONGYANJI), or a `抖音@xxx` watermark. A small logo printed on the mask fabric is OK. Unrelated props (a drink pouch) are OK if nothing on them is legible. |
| tạo voice over tiếng Anh | If an `.mp3`/`.wav` VO is already in the folder, transcribe it and check the text against the script; don't regenerate. Otherwise generate one with the ElevenLabs TTS skill from the script. Mute all source audio. |
| chạy phụ đề tự động, karaoke, chữ trắng viền đen | `helpers/karaoke_ass.py` (style below). |

## Pipeline

1. **Inventory.** `ffprobe` every file. Sources are usually 576×1024 or 720×1280 at 30fps, with Chinese filenames. Read `edit/project.md` if it exists.
2. **VO transcript.** `video-use/helpers/transcribe.py <vo.mp3>` gives word-level Scribe JSON (cached). Diff it against the script.
3. **Shot selection.** Coarse look at candidates, then **dense-sample every exact cut window at 2fps** before trusting it. Box flashes and watermarks hide between coarse samples; this was missed twice at 0.5fps. Prefer splitting a clip around a box flash to discarding the clip.
4. **Base video.** Extract each range scaled/cropped to 1080×1920 30fps, with no audio. Concat losslessly into `edit/base_video.mp4`. Segment durations must add up to the VO length; an optional 2–3s silent "reveal" tail after the VO ends is good.
5. **Audio.** VO, plus optional upbeat music ducked under the voice (`sidechaincompress` with the VO as the key; `asplit` the VO first). Then two-pass loudnorm to −14 LUFS / −1 dBTP. Mux at the end; never take audio from the source clips.
6. **Caption bands.** Run `helpers/detect_captions.py` → `bands.json` (see "Cover bands"). Eyeball one frame per band, then run `helpers/edge_check.py` and eyeball every hit.
7. **Karaoke captions.** `helpers/karaoke_ass.py <vo transcript> --bands bands.json` → `master_karaoke.ass`.
8. **Render.** `helpers/render_snug.py base_video.mp4 bands.json master_karaoke.ass --audio <mix> -o final.mp4`.
9. **Verify before showing** (details below).

## Karaoke caption style (approved)

- Arial Black 66 on a 1080×1920 canvas, UPPERCASE, trailing punctuation stripped.
- **White text, black outline 4, shadow 1.** The word being spoken sweeps to **yellow #FFE600** (`\kf`); words not yet spoken stay white.
- Each cue holds about 3 words, max 4, and closes early on punctuation, a pause of 0.3s or more, or when the estimated width passes 940px. Never wrap, and never shrink the font to make a long cue fit. Long words get their own cue.
- 60ms fade-in. A cue is held until the next one starts when the gap is under 0.35s, so captions don't flicker.
- Each cue is centred inside the blur band active at its start time (`\an5\pos(540, band centre)`). Where there's no band, the centre is y=1455 (~76%).

## Cover bands (approved)

- **Snug, one per source clip:** the measured caption extent plus **~22px padding** above and below, full width, gated to that segment's time range. Don't gate per cue, or old text flashes through during pauses.
- **No darkening.** Use `boxblur=22:2` and `saturation=0.55` only. The earlier `eq=brightness=-0.18` over a 60–100% band was rejected as "mọi thứ rất tối". The desaturation stops yellow Chinese captions from bleeding through as a yellow smear.
- Segments with no burned-in text get no band.
- `detect_captions.py` finds bright text pixels that sit next to a dark outline. It drops outlier detections (inset photos, logos, white props), and it grows a line to include a sparse second line (a single "了"). That second-line case leaked by 4px before the growth step was added. Use `--merge i-j` when consecutive segments come from the same source clip, so they share one band.
- Expect false hits from hair, white clothing edges, and printed fabric. Eyeball every hit; don't widen bands blindly.

## Verification bar

- A 1fps full-frame sweep of the whole render for packaging, watermarks, and legible Chinese anywhere.
- A 2fps sweep of the band region, plus `edge_check.py` (4fps, 80px strips and 12px edge slices around every band).
- Hit or near-miss timestamps get a full-res crop check.
- `ffmpeg -af ebur128` should give about −14 LUFS integrated.
- Check that `ffprobe` duration equals the VO length plus the tail.

## Machine gotchas (macOS, this setup)

- The `ass`, `subtitles` and `drawtext` filters need **`/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`**. Plain brew `ffmpeg` has no libass or freetype.
- The system `python3` has no numpy or PIL. Run the helpers with `uv run --project ~/.claude/skills/video-use python ...`.
- The shell is zsh: write `${top}` inside strings, never `$top:enable`, because `:e` is a zsh modifier and silently eats characters.
- Contact sheets made with `fps=1,tile` after `-ss`/`-t` returned the wrong time range. Extract single frames with `-ss T -frames:v 1` and tile them in time order.
- `rm` with globs inside `cd` gets blocked by the safety check. Overwrite files instead, or leave the cleanup to the creator.

## Deliverable

Write `edit/final_karaoke.mp4` (or whatever name the creator asks for). Keep `bands.json`, `master_karaoke.ass`, and `project.md` next to it, and append a session entry to `project.md`.
