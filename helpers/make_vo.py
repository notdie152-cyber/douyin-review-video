"""Stage 2 - voiceovers + word timings. For every video in plan.json["_videos"], TTS scripts/sN.txt with the
creator's default ElevenLabs voice, then Scribe-transcribe it (video-use's transcribe.py, cached).

  python3 make_vo.py            # all videos;  --voice <id> to override
"""
import argparse, concurrent.futures as cf, json, os, re, subprocess, sys, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import B, plan

DEFAULT_VOICE = "BPLivKkO9sN6vs4a43o2"          # "Beauty" - the creator's cloned voice (standing default)
VIDEO_USE = os.path.expanduser("~/.claude/skills/video-use")


def key():
    k = os.environ.get("ELEVENLABS_API_KEY")
    if not k:
        for line in open(os.path.join(VIDEO_USE, ".env")):
            if line.startswith("ELEVENLABS_API_KEY"):
                k = line.split("=", 1)[1].strip().strip('"\'')
    return k


def tts(n, voice):
    out = f"{B}/vo/vo{n}.mp3"
    if os.path.exists(out):
        return out
    text = re.sub(r"[™®©]", "", open(f"{B}/scripts/s{n}.txt").read().strip())
    body = json.dumps({"text": text, "model_id": "eleven_multilingual_v2",
                       "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True}}).encode()
    # mp3_44100_192 needs the Creator tier; this account gets 128
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
                                 data=body, headers={"xi-api-key": key(), "Content-Type": "application/json"})
    try:
        open(out, "wb").write(urllib.request.urlopen(req, timeout=300).read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"TTS failed for script {n}: {e.read()[:300]}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--voice", default=DEFAULT_VOICE); a = ap.parse_args()
    os.makedirs(f"{B}/vo", exist_ok=True)
    ns = sorted({v["script"] for v in plan()["_videos"].values()})
    with cf.ThreadPoolExecutor(3) as ex:
        paths = list(ex.map(lambda n: tts(n, a.voice), ns))
    for p in paths:
        subprocess.run(["uv", "run", "--project", VIDEO_USE, "python", f"{VIDEO_USE}/helpers/transcribe.py", p,
                        "--edit-dir", B], check=True, stdout=subprocess.DEVNULL)
        print(p, "->", f"transcripts/{os.path.basename(p)[:-4]}.json")
