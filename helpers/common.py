"""Shared paths for the batch pipeline. Every batch script runs with the cwd = the batch dir
(e.g. <videos_dir>/edit/batch). Layout inside it:

  plan.json            shot plan + per-video config (see SKILL.md "Batch mode")
  scripts/sN.txt       script text, one sentence per line
  vo/voN.mp3           voiceovers          transcripts/voN.json  Scribe word timings
  scan/                sources.json, fr/<id>/ (2fps frames), ocrjson/<id>.jsonl, analysis.json, windows.json
  <Name>/              edl.json, clips/, base.mp4, mix.wav, segocr/, bands.json, karaoke.ass
  leak_boxes.json      leak feedback from render OCR
"""
import json, os, subprocess

B = os.getcwd()
SCAN = os.path.join(B, "scan")
HELPERS = os.path.dirname(os.path.abspath(__file__))
FF = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"     # plain brew ffmpeg lacks libass/drawtext
OCR_SRC = os.path.join(HELPERS, "vision_ocr.swift")
OCR = os.path.expanduser("~/.cache/douyin-review-video/vision_ocr")


def ocr_bin():
    """compile the Apple Vision OCR tool on first use"""
    if not os.path.exists(OCR) or os.path.getmtime(OCR) < os.path.getmtime(OCR_SRC):
        os.makedirs(os.path.dirname(OCR), exist_ok=True)
        subprocess.run(["swiftc", "-O", OCR_SRC, "-o", OCR], check=True)
    return OCR


def plan():
    return json.load(open(os.path.join(B, "plan.json")))


def sources():
    return json.load(open(os.path.join(SCAN, "sources.json")))


def run(cmd):
    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                capture_output=True, text=True).stdout)
