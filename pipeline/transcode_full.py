#!/usr/bin/env python3
"""Transcode every video at FULL length (tonemapped, rotation-corrected)
into media/videos_full/ so the site can trim at playback time."""
import json, os, subprocess

SP = os.path.dirname(os.path.abspath(__file__))
SRC = "/Volumes/SSK SSD/Applications/Alaska Cruise Timeline Ordered - Both Phones"
DST = "/Volumes/SSK SSD/Applications/Alaska Cruise Slideshow Site/media/videos_full"
os.makedirs(DST, exist_ok=True)

# files whose rotation side-data is wrong and must be ignored (user-verified)
IGNORE_ROTATION = {"0466_2026-06-06_212317Z_video_gary_IMG_2645.MOV"}
TRANSPOSE = {90: "cclock", 180: "reversal", 270: "clock"}

def probe(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:stream_side_data=rotation", "-of", "json", path],
        capture_output=True, text=True)
    d = json.loads(r.stdout)["streams"][0]
    w, h = d["width"], d["height"]
    rot = 0
    for sd in d.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(sd["rotation"]) % 360
    if rot % 180 != 0:
        w, h = h, w
    return w, h, rot

items = json.load(open(os.path.join(SP, "metadata.json")))
videos = [it for it in items if it["type"] == "video"]
fails = 0
for i, it in enumerate(videos):
    src = os.path.join(SRC, it["file"])
    base = os.path.splitext(it["file"])[0]
    out = os.path.join(DST, base + ".mp4")
    if os.path.exists(out) and os.path.getsize(out) > 100_000:
        print(f"[{i+1}/{len(videos)}] skip {base}", flush=True)
        continue
    w, h, rot = probe(src)
    if it["file"] in IGNORE_ROTATION:
        rot = 0
        if w < h:
            w, h = h, w
    if w >= h:
        tw = min(w, 1920); th = int(tw * h / w) & ~1; tw &= ~1
    else:
        th = min(h, 1920); tw = int(th * w / h) & ~1; th &= ~1
    vf = f"scale_vt=w={tw}:h={th}:color_matrix=bt709:" \
         "color_primaries=bt709:color_transfer=bt709"
    if rot in TRANSPOSE:
        vf = f"transpose_vt=dir={TRANSPOSE[rot]}," + vf
    cmd = ["ffmpeg", "-y", "-v", "error", "-noautorotate",
           "-hwaccel", "videotoolbox", "-hwaccel_output_format", "videotoolbox_vld",
           "-i", src, "-vf", vf, "-metadata:s:v", "rotate=0",
           "-c:v", "h264_videotoolbox", "-b:v", "5M",
           "-c:a", "aac", "-b:a", "128k", "-ac", "2",
           "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        fails += 1
        print(f"[{i+1}/{len(videos)}] FAILED {base}: {r.stderr.strip()[:200]}",
              flush=True)
    else:
        print(f"[{i+1}/{len(videos)}] ok {base}", flush=True)
print(f"done, {fails} failures")
