# douyin-review-video

A Claude Code skill that turns scraped Douyin/TikTok product clips and an English script or voiceover into an English product-review ad (1080×1920). It works on top of [video-use](https://github.com/browser-use/video-use).

- Uses highlight shots only, and drops any shot that shows Chinese packaging or brand text.
- Covers burned-in Chinese captions with snug blur bands, measured automatically per clip.
- Burns in karaoke captions in **Fira Sans Condensed Black Italic** (bundled; Phudu Black also included): white text, black outline, and the spoken word sweeps to yellow.
- Replaces the audio with the English voiceover, plus optional music ducked under the voice, mastered to −14 LUFS.

## Install

```bash
git clone https://github.com/notdie152-cyber/douyin-review-video.git
ln -s "$PWD/douyin-review-video" ~/.claude/skills/douyin-review-video
```

Requirements:
- the video-use skill, installed with its `.venv` (numpy and Pillow come from there);
- `brew install ffmpeg-full`, needed for the libass and drawtext filters;
- an ElevenLabs API key, in video-use's `.env`.

## Helpers

| Script | Purpose |
|---|---|
| `helpers/detect_captions.py` | Measure burned-in caption rows per segment and write `bands.json` |
| `helpers/edge_check.py` | Zero-leak scan of the strips just outside each band |
| `helpers/karaoke_ass.py` | Turn a Scribe word transcript into karaoke ASS captions centred in the bands |
| `helpers/render_snug.py` | Blur bands → captions → audio mux, producing the final MP4 |

See `SKILL.md` for the full pipeline and the approved values.

## Font license

- `fonts/FiraSansCondensed-BlackItalic.ttf` is [Fira Sans](https://github.com/mozilla/Fira) © 2012-2015 The Mozilla Foundation and Telefonica S.A., licensed under the SIL Open Font License 1.1 (see `fonts/OFL-FiraSans.txt`).
- `fonts/Phudu-Black.ttf` is [Phudu](https://github.com/duongtrtype/DTPhudu) © 2022 The Phudu Project Authors, licensed under the SIL Open Font License 1.1 (see `fonts/OFL-Phudu.txt`).
