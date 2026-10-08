# douyin-review-video

A Claude Code skill that turns scraped Douyin/TikTok product clips and an English script or voiceover into an English product-review ad (1080×1920). It works on top of [video-use](https://github.com/browser-use/video-use).

- Uses highlight shots only, and drops any shot that shows Chinese packaging or brand text.
- Covers burned-in Chinese captions with snug blur bands, measured automatically per clip.
- Burns in karaoke captions in **Fira Sans Condensed Black Italic** (bundled; Phudu Black also included): white text, black outline, and the spoken word sweeps to yellow.
- Replaces the audio with the English voiceover, plus optional music ducked under the voice, mastered to −14 LUFS.
- Batch mode: N separate videos (one script each) from one folder of clips.

Requires macOS, because OCR uses Apple Vision through `swiftc`.

## Install

```bash
git clone https://github.com/notdie152-cyber/douyin-review-video.git
ln -s "$PWD/douyin-review-video" ~/.claude/skills/douyin-review-video
```

Requirements:
- the video-use skill, installed with its `.venv` (numpy and Pillow come from there);
- `brew install ffmpeg-full`, needed for the libass and drawtext filters;
- an ElevenLabs API key, in video-use's `.env`.

## Pipeline

Run every stage from `<videos_dir>/edit/batch/`, using `uv run --project ~/.claude/skills/video-use python <helper>`:

| Stage | Helper | What it does |
|---|---|---|
| 1 | `scan_sources.py <videos_dir>` | Extracts every clip at 2fps and OCRs it (Apple Vision), finds clean windows, writes contact sheets and drops clips with watermarks |
| 2 | `scan_sources.py --strips ranges.json` | Builds 2fps strips for checking candidate ranges by eye |
| 3 | *(write `plan.json`)* | Lists clean ranges per script sentence for each video |
| 4 | `make_vo.py` | Generates the voiceover with ElevenLabs (default voice "Beauty") and gets Scribe word timings |
| 5 | `build_batch.py Name… [--plan-only]` | Cuts line-aligned shots on whole frames and builds the VO + ducked-music mix at −14 LUFS |
| 6 | `seg_bands.py Name…` | Builds snug blur bands from 10fps OCR of each shot and flags packaging text |
| 7 | `build_batch.py Name… --finish` | Adds karaoke captions centred in the bands and renders the final video |
| 8 | `verify_leaks.py Name…` | OCRs the render at 10fps and feeds any leaked Chinese back into stage 6 |

Shared: `common.py` holds the paths, `karaoke_ass.py` builds the captions, `render_snug.py` does the final composite, and `vision_ocr.swift` is the OCR tool. `detect_captions.py` and `edge_check.py` are a pixel-based fallback for when OCR is unavailable.

## Font license

- `fonts/FiraSansCondensed-BlackItalic.ttf` is [Fira Sans](https://github.com/mozilla/Fira) © 2012-2015 The Mozilla Foundation and Telefonica S.A., licensed under the SIL Open Font License 1.1 (see `fonts/OFL-FiraSans.txt`).
- `fonts/Phudu-Black.ttf` is [Phudu](https://github.com/duongtrtype/DTPhudu) © 2022 The Phudu Project Authors, licensed under the SIL Open Font License 1.1 (see `fonts/OFL-Phudu.txt`).
