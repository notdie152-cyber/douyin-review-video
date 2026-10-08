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
| tạo voice over tiếng Anh | If an `.mp3`/`.wav` VO is already in the folder, transcribe it and check the text against the script; don't regenerate. Otherwise generate it with **the default voice "Beauty", `voice_id BPLivKkO9sN6vs4a43o2`** (the creator's cloned voice), unless they name another. Mute all source audio. |
| chạy phụ đề tự động, karaoke, chữ trắng viền đen | Karaoke captions (style below), centred in the blur band. |
| làm N video riêng biệt … xuất Scale8, Scale9… | One script per video, 5–6 of the best clips each, output named exactly as asked. One video is just N=1. |

## Pipeline (one video or many)

All stages run with **cwd = `<videos_dir>/edit/batch/`** and write nothing outside it except the final MP4s. Run Python helpers with `uv run --project ~/.claude/skills/video-use python ~/.claude/skills/douyin-review-video/helpers/<script>` (system `python3` has no numpy or PIL; `karaoke_ass.py` and `render_snug.py` need no extra packages). `helpers/common.py` documents the folder layout. The Apple Vision OCR tool (`vision_ocr.swift`, zh-Hans + en) compiles itself to `~/.cache/douyin-review-video/` on first use.

1. **Scan:** `scan_sources.py <videos_dir>`. This extracts every vertical clip at 2fps and OCRs it, then writes `scan/analysis.json` with, per frame: the Chinese caption lines, the *dirty* text (any other CJK, or brand words), and the share of orange (mask) pixels. It also writes `scan/windows.json` (clean windows that skip the first 0.2s and keep ±0.5s from dirty frames) and contact sheets `scan/sheet_N.jpg`. **Clips that show a creator watermark** (`抖音|博主|号：|搬运|@`) are skipped outright.
2. **Pick shots by eye.** OCR misses text that is too small at 540px (sachets, boxes) and text-free bandages from other brands. Read every sheet and tag shot types: puffy/sagging before shot, side sleeping, stretching the fabric, ear loops, wearing, chores while wearing, peel-off, bare-face result, cold tools (roller/gua sha). Then run `scan_sources.py --strips ranges.json` on the candidates, read the 2fps strips, and write down exact clean sub-ranges.
3. **Write `plan.json`.** For each video, list one set of `[src, a, b]` ranges per **script sentence**, matched to its meaning, plus `_videos.<Name>.script` (N → `scripts/sN.txt`) and a few `spares`. `_music` is optional, `_out` is the output folder. Hook and problem lines run 7–12s, so give each line at least its VO length in footage. Keep each video's main clips different from the other videos'. Format is in `build_batch.py`'s docstring.
4. **Voiceover:** `make_vo.py`. TTS uses the default voice (below), then Scribe word timings → `transcripts/voN.json`. If the creator supplied a VO file, put it at `vo/voN.mp3` and it is reused, not regenerated.
5. **Cut:** `build_batch.py <Names…>`. Script sentences are aligned to Scribe words (difflib) to get line spans. Each span is filled with shots of 1.0–3.8s, round-robin over that line's ranges; slivers under 0.8s are absorbed into a neighbour; ranges are clamped to `source_dur - 0.1`. Cuts are **whole frames** (`-frames:v N` at 30fps), and the frame count of every clip is asserted, because one short clip makes every later cut drift. The audio is the VO plus music ducked under it (sidechaincompress), two-pass loudnorm to −14 LUFS / −1 dBTP; source audio is never used. Use `--plan-only` to preview shot stats first.
6. **Bands:** `seg_bands.py <Names…>` (rules below). It also prints `!!` for any shot whose 10fps OCR shows **non-subtitle text** (packaging, brand, ingredient card, patent). View each one; if it is real, replace that range in `plan.json` and go back to step 5. Never blur packaging.
7. **Render:** `build_batch.py <Names…> --finish` → karaoke ASS centred in the bands → `render_snug.py` → `<_out>/<Name>.mp4`.
8. **Verify:** `verify_leaks.py <Names…>`. It OCRs the render at 10fps. `LEAK` hits (confidence ≥ 0.5, Chinese outside a band) are fed back with their timestamp into `leak_boxes.json`; then repeat steps 6–8 until it prints `new leaks fed back: 0`. Look at every `check` hit by eye (usually shirt prints, or our caption merged with background). Then do the rest of the verification bar.

## Cover bands (approved 2026-10-08)

The creator rejected two earlier versions: a dark 60–100% band ("mọi thứ rất tối"), and stacked bands from unioning every caption seen near a shot ("quá nhiều lớp phủ mờ thừa thãi"). What they approved:

- Bands come from **10fps OCR of exactly the frames each shot uses**. `seg_bands.py` extracts `ceil(nf/3)` frames after `select=not(mod(n,3))`; using `nf` would read 3× past the shot.
- **One band per caption line position per shot:** line extent + 20px padding, at least 120px tall, full width. Merge two lines only when they are on screen together within 30px (a 2-line caption). At most one band is on screen at a time, apart from a genuine 2-line caption.
- **Timing:** a band covers the whole shot if its caption shows in ≥25% of the shot's frames. Otherwise it runs from first to last appearance ±0.3s, snapped to the cut when within 0.5s of it.
- **Fallback:** if OCR sees nothing in a shot but the clip normally has captions, use the clip's dominant caption line from the 2fps full-clip scan.
- **Look:** `boxblur=22:2` with `saturation=0.55`, no darkening. Desaturating stops yellow Chinese captions showing through as a smear. `render_snug.py` clamps the blur radius to `band_h/4-1`; thinner bands otherwise crash ffmpeg.
- A shot with no burned-in text gets no band.
- `detect_captions.py` and `edge_check.py` are the older pixel-based detectors (bright text next to a dark outline). They are a fallback only when OCR is unavailable.

## Verification bar

- `verify_leaks.py` reports 0 new leaks, and every `check` hit has been viewed.
- A frame sweep of each render (every ~1.5s): no packaging, box, sachet or watermark anywhere; one snug band per shot; caption centred in it. Look at the frames yourself before reporting.
- `ffmpeg -af ebur128` gives about −14 LUFS integrated and a true peak ≤ −1 dBTP.
- `ffprobe` duration equals the VO length + 1s tail. You cannot listen to the audio, so say so when reporting.
- Append a session entry to `edit/project.md`.

## Karaoke caption style (approved)

- **Font: Fira Sans Condensed Black Italic** (`fonts/FiraSansCondensed-BlackItalic.ttf`, SIL OFL, `fonts/OFL-FiraSans.txt`). This is the font of the creator's CapCut reference `mat1.mov`. Mask-matching against about 500 Google Fonts (upright, italic, and faux-italic) put it on top, and a by-eye check confirmed the G with a spur, the straight-legged R, and the rounded S/U. It uses the font's **real italic face** (`Italic=-1` in the ASS style, resolved from fontsdir), not a libass faux slant. Letter widths match mat1 within 1–4% at normal spacing.
- `render_snug.py` passes `fontsdir=<skill>/fonts` to libass, so nothing needs installing. If you render the ASS any other way, pass the same `fontsdir`, or libass silently falls back to another face. Check by running ffmpeg with `-v verbose` and looking for `Loading font file '.../FiraSansCondensed-BlackItalic.ttf'`.
- The alternative bundled face is **Phudu Black** (`fonts/Phudu-Black.ttf`, OFL), cloned from `video-chua-font-chu.mp4`: upright, condensed, with a curved-arm Y. Use it when the creator asks for that look: `--font "Phudu Black" --italic 0 --size 80 --px-per-char 40`.
- Size 84 on a 1080×1920 canvas gives about 50px of yellow fill height, the same as mat1. UPPERCASE, trailing punctuation stripped.
- **White text, black outline 6, shadow 2.** The word being spoken sweeps to **yellow #FFE600** (`\kf`); words not yet spoken stay white.
- Each cue holds about 3 words, max 4, and closes early on punctuation, a pause of 0.3s or more, or when the estimated width passes 940px (41px per character for Fira at size 84). Never wrap, and never shrink the font to make a long cue fit. Long words get their own cue.
- 60ms fade-in. A cue is held until the next one starts when the gap is under 0.35s, so captions don't flicker.
- Each cue is centred inside the active blur band (`\an5\pos(540, band centre)`). If the band changes during a cue (a cut), the cue is **split** there and moves with it: words already sung get `\kf0`, the current word keeps sweeping. With no band, captions sit at the video's median band centre.

### Cloning a font from another reference video

If the creator sends a new reference video, identify its font by shape, not by eye:
1. Build a text mask from the reference: bright white or yellow pixels whose surrounding ring is mostly dark outline (connected components, keeping only those with more than 50% dark pixels in the ring).
2. Pull the family list from `https://fonts.google.com/metadata/fonts`, keeping families with the `vietnamese` subset that are Display, or Sans Serif with weight ≥ 700. Download the heaviest weight of each via `fonts.googleapis.com/css2?family=X:wght@N` (an old User-Agent gets you TTF).
3. Render the same line in every font and score it as mask IoU × (aspect-ratio similarity)². Then compare the top 8 by eye against the real crop: distinctive glyphs (Y, G, Q, Ư) decide it.
4. Bundle the font only if it is OFL or Apache licensed, together with its license file (`fonts/OFL-<Name>.txt`).
5. For italic references, also download the `ital,wght@1,<max>` face. Score upright fonts with a 0.2–0.26 shear as well, and prefer a real italic face over faux italic when both match.
6. Measure the rendered fill height using only our own fill colour (the source's old captions contaminate a naive bbox), then scale `--size` to match the reference.

## Machine gotchas (macOS, this setup)

- The `ass`, `subtitles` and `drawtext` filters need **`/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`**. Plain brew `ffmpeg` has no libass or freetype.
- The system `python3` has no numpy or PIL. Run the helpers with `uv run --project ~/.claude/skills/video-use python ...`.
- The shell is zsh: write `${top}` inside strings, never `$top:enable`, because `:e` is a zsh modifier and silently eats characters.
- Contact sheets made with `fps=1,tile` after `-ss`/`-t` returned the wrong time range. Extract single frames with `-ss T -frames:v 1` and tile them in time order.
- `rm` with globs inside `cd` gets blocked by the safety check. Overwrite files instead, or leave the cleanup to the creator.


## ElevenLabs TTS (defaults)

- **Voice:** "Beauty", `BPLivKkO9sN6vs4a43o2`. This is the creator's standing default.
- `POST /v1/text-to-speech/{voice_id}?output_format=mp3_44100_128` with `model_id: eleven_multilingual_v2` and `voice_settings: {stability 0.45, similarity_boost 0.8, style 0.25, use_speaker_boost true}`.
- The key in `video-use/.env` **lacks `voices_read`**, so you can't list or search voices: ask for an ID instead of guessing. The plan is below Creator tier, so `mp3_44100_192` is refused; use 128.
- Strip `™` and similar symbols from the script before sending. `helpers/make_vo.py` does TTS + Scribe transcription for every script in one go.
