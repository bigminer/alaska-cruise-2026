#!/usr/bin/env python3
"""Cut every USED video down to just its trimmed [start, start+len] window
into media/videos_web/ so the whole site fits on GitHub Pages.

Sources are the already-processed (rotation/tonemap-corrected) clips in
media/videos_full/, so we only need to cut + re-encode the short window.
Reads the trim windows straight from data.js."""
import json, os, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(ROOT, "media", "videos_web")
os.makedirs(DST, exist_ok=True)


def load_video_slides():
    s = open(os.path.join(ROOT, "data.js")).read()
    s = s[s.index("{"):s.rindex("}") + 1]
    d = json.loads(s)
    out = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("type") == "video":
                out.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    return out


vids = load_video_slides()
fails = 0
for i, it in enumerate(vids):
    src = os.path.join(ROOT, it["src"])
    base = os.path.splitext(os.path.basename(it["src"]))[0]
    out = os.path.join(DST, base + ".mp4")
    start = float(it["trim"]["start"])
    length = float(it["trim"]["len"])
    if os.path.exists(out) and os.path.getsize(out) > 50_000:
        print(f"[{i+1}/{len(vids)}] skip {base}", flush=True)
        continue
    # -ss before -i for a fast seek; re-encode gives a frame-accurate cut.
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-ss", f"{start}", "-i", src, "-t", f"{length}",
           "-c:v", "h264_videotoolbox", "-b:v", "5M",
           "-c:a", "aac", "-b:a", "128k", "-ac", "2",
           "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        fails += 1
        print(f"[{i+1}/{len(vids)}] FAILED {base}: {r.stderr.strip()[:200]}",
              flush=True)
    else:
        sz = os.path.getsize(out) / 1e6
        print(f"[{i+1}/{len(vids)}] ok {base}  ({sz:.1f} MB)", flush=True)
print(f"done, {fails} failures")
