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

- **Font: Fira Sans Condensed Black Italic** (`fonts/FiraSansCondensed-BlackItalic.ttf`, SIL OFL, `fonts/OFL-FiraSans.txt`). This is the font of the creator's CapCut reference `mat1.mov`. Mask-matching against about 500 Google Fonts (upright, italic, and faux-italic) put it on top, and a by-eye check confirmed the G with a spur, the straight-legged R, and the rounded S/U. It uses the font's **real italic face** (`Italic=-1` in the ASS style, resolved from fontsdir), not a libass faux slant. Letter widths match mat1 within 1–4% at normal spacing.
- `render_snug.py` passes `fontsdir=<skill>/fonts` to libass, so nothing needs installing. If you render the ASS any other way, pass the same `fontsdir`, or libass silently falls back to another face. Check by running ffmpeg with `-v verbose` and looking for `Loading font file '.../FiraSansCondensed-BlackItalic.ttf'`.
- The alternative bundled face is **Phudu Black** (`fonts/Phudu-Black.ttf`, OFL), cloned from `video-chua-font-chu.mp4`: upright, condensed, with a curved-arm Y. Use it when the creator asks for that look: `--font "Phudu Black" --italic 0 --size 80 --px-per-char 40`.
- Size 84 on a 1080×1920 canvas gives about 50px of yellow fill height, the same as mat1. UPPERCASE, trailing punctuation stripped.
- **White text, black outline 6, shadow 2.** The word being spoken sweeps to **yellow #FFE600** (`\kf`); words not yet spoken stay white.
- Each cue holds about 3 words, max 4, and closes early on punctuation, a pause of 0.3s or more, or when the estimated width passes 940px (41px per character for Fira at size 84). Never wrap, and never shrink the font to make a long cue fit. Long words get their own cue.
- 60ms fade-in. A cue is held until the next one starts when the gap is under 0.35s, so captions don't flicker.
- Each cue is centred inside the blur band active at its start time (`\an5\pos(540, band centre)`). Where there's no band, the centre is y=1455 (~76%).

### Cloning a font from another reference video

If the creator sends a new reference video, identify its font by shape, not by eye:
1. Build a text mask from the reference: bright white or yellow pixels whose surrounding ring is mostly dark outline (connected components, keeping only those with more than 50% dark pixels in the ring).
2. Pull the family list from `https://fonts.google.com/metadata/fonts`, keeping families with the `vietnamese` subset that are Display, or Sans Serif with weight ≥ 700. Download the heaviest weight of each via `fonts.googleapis.com/css2?family=X:wght@N` (an old User-Agent gets you TTF).
3. Render the same line in every font and score it as mask IoU × (aspect-ratio similarity)². Then compare the top 8 by eye against the real crop: distinctive glyphs (Y, G, Q, Ư) decide it.
4. Bundle the font only if it is OFL or Apache licensed, together with its license file (`fonts/OFL-<Name>.txt`).
5. For italic references, also download the `ital,wght@1,<max>` face. Score upright fonts with a 0.2–0.26 shear as well, and prefer a real italic face over faux italic when both match.
6. Measure the rendered fill height using only our own fill colour (the source's old captions contaminate a naive bbox), then scale `--size` to match the reference.

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


## ElevenLabs TTS (defaults)

- **Voice:** "Beauty", `BPLivKkO9sN6vs4a43o2`. This is the creator's standing default.
- `POST /v1/text-to-speech/{voice_id}?output_format=mp3_44100_128` with `model_id: eleven_multilingual_v2` and `voice_settings: {stability 0.45, similarity_boost 0.8, style 0.25, use_speaker_boost true}`.
- The key in `video-use/.env` **lacks `voices_read`**, so you can't list or search voices: ask for an ID instead of guessing. The plan is below Creator tier, so `mp3_44100_192` is refused; use 128.
- Strip `™` and similar symbols from the script before sending. Transcribe the generated VO with Scribe (`video-use/helpers/transcribe.py --edit-dir <batch>`) to get word timings for captions and line-level cuts.

## Batch mode: N videos from one folder of clips

Use this when the creator asks for several separate videos (e.g. "làm 6 video riêng biệt … xuất Scale8, Scale9…"), each built from 5–6 of the best source clips, one script per video.

1. **Scan every clip automatically.** Extract frames at 2fps (540 wide, using `ffmpeg -nostdin`, or ffmpeg eats a shell `while read` loop's stdin and mangles the IDs). Run `helpers/vision_ocr.swift` on them: compile it with `swiftc -O vision_ocr.swift -o vision_ocr`. It uses Apple Vision `zh-Hans`+`en-US` and outputs one JSON line per frame with text boxes. Per frame, record:
   - Chinese caption lines: CJK text, y 0.45–0.97, centred, h < 0.07 → caption bands later.
   - Everything else that is CJK, or a brand word (`TONG|YANJ|COLL|TRIP|PEPT|FIRM|MOIST|SERUM|HYAL|\d+G`) → reject the frame plus ±0.5s. Mirrored t-shirt prints (e.g. "ILMAYOMOT") are false positives.
   - The share of orange pixels (`R>190, 80<G<175, B<90, R-G>50`): mask on screen means a highlight.
2. **OCR is not enough on its own.** White sachets and boxes carry text too small to read at 540px, and other brands' bandages have no text at all. Build contact sheets of the clean windows (4 frames each) and tag shot types by eye: puffy/sagging before shot, side sleeping, stretching the fabric, ear loops, wearing, chores while wearing, peel-off, bare-face result, cold tools (roller/gua sha). Then build **2fps strips of every candidate range** and write down exact clean sub-ranges.
3. **Plan per script line.** Each script sentence gets a list of `[src, start, end]` ranges matched to its meaning, stored in `plan.json`, plus a small spare list per video. Hook and problem lines run long (7–12s each), so give them ≥ the line's VO length in footage. Keep each video's main clips different from the other videos'.
4. **Assemble** with `helpers/build_batch_example.py`, which shows the working pattern. It aligns script lines to Scribe words with difflib to get line spans. It fills each span with shots of 1.0–3.8s, round-robin across that line's ranges, and absorbs slivers under 0.8s into a neighbour. For each segment it takes the caption **y-clusters** from the OCR boxes, using only frames inside the segment (±0.25s), so one stray line can't create a 900px band. It uses one fixed caption height per video (the median caption centre), merges our caption into a band when it is within 140px, then runs mix → karaoke → `render_snug.py`.
5. **Output** to `<videos_dir>/output/<Name>.mp4`, then run the normal verification bar on every file.
6. **Snug bands (approved 2026-10-08, after "quá nhiều lớp phủ mờ thừa thãi").** Build the bands from **10fps OCR of exactly the frames each shot uses** (`helpers/seg_bands.py`: extract with `-frames:v ceil(nf/3)` after `select=not(mod(n,3))`; getting this count wrong reads 3× past the shot). Rules:
   - Each caption line position in a shot gets **one band**: the line extent plus 20px of padding, at least 120px tall. Stack lines only when they are on screen together within 30px (a 2-line caption). Never take the union of everything near the shot; that is what produced the stacked bands the creator rejected.
   - A band covers the whole shot if its caption shows in ≥25% of the shot's frames. Otherwise it runs from its first to last appearance ±0.3s, snapped to the cut when within 0.5s of it.
   - If OCR finds nothing in a shot but the clip normally has captions, fall back to the clip's dominant caption line from the full-clip scan.
   - At most one band is on screen at a time, except for a genuine 2-line caption.
   - The English caption is centred in the active band. `karaoke_ass.py --bands` **splits a cue at a band change**: words already sung get `\kf0`, the current word continues, and the line moves with the cut.
7. **Verify, then feed back.** OCR the render at 10fps and run `helpers/leak_feedback.py`. It adds every Chinese hit with confidence ≥0.5 that lies outside a band, *with its time*, to `leak_boxes.json`. Re-run `seg_bands.py` and the render until it reports 0. Look at low-confidence hits by eye; they are usually shirt prints or our own caption merged with background.
8. **Pitfalls found in this batch:**
   - **A range past the end of the source** produces a short clip, and every later cut drifts (5 frames = bands 0.17s late). Clamp ranges to `source_dur - 0.1` and count frames per clip after extraction.
   - **Box flashes 3–4 frames long at a cut.** Cut on whole frames, and start every shot ≥0.2s into a source, because the creator's own sticker or title card often sits in the first frames.
   - **Creator watermarks** (`高小高`, `抖音号：黄多多`, `博主：张大正`, `抖音@xxx搬运必究`): drop those sources outright.
   - **Packaging hidden under oversized bands.** Once bands are snug, re-check every shot for packaging text (`TONGYANJI`, `专利`, `净含量`, `FIRM SKIN`, ingredient infographics) with the per-shot 10fps OCR, and swap the shot out rather than blurring it.
   - `render_snug.py` clamps the boxblur radius to `band_h/4-1`; thinner bands otherwise crash ffmpeg.
