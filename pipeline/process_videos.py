#!/usr/bin/env python3
"""For each video: find the most interesting 10s window (audio energy + motion),
transcode it to web H.264 with VideoToolbox HDR->SDR tonemapping.
Writes clips.json with chosen windows."""
import json, os, re, subprocess, sys

SP = os.path.dirname(os.path.abspath(__file__))
SRC = "/Volumes/SSK SSD/Applications/Alaska Cruise Timeline Ordered - Both Phones"
DST = "/Volumes/SSK SSD/Applications/Alaska Cruise Slideshow Site/media/videos"
os.makedirs(DST, exist_ok=True)

CLIP = 10.0

def probe_stream(path):
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
    has_audio = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a", "-show_entries",
         "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True).stdout.strip() != ""
    return w, h, rot, has_audio

# rotation side-data (degrees, CCW-positive) -> transpose_vt dir
TRANSPOSE = {90: "cclock", 180: "reversal", 270: "clock"}

def audio_energy(path):
    """RMS level per ~0.5s -> list of (t, rms_db)."""
    r = subprocess.run(
        ["ffmpeg", "-v", "quiet", "-i", path, "-map", "0:a:0",
         "-af", "aresample=48000,asetnsamples=24000,"
                "astats=metadata=1:reset=1,"
                "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
         "-f", "null", "-"], capture_output=True, text=True)
    out = []
    t = None
    for line in r.stdout.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1)); continue
        m = re.search(r"RMS_level=(-?[\d.]+|-inf)", line)
        if m and t is not None:
            v = -90.0 if m.group(1) == "-inf" else max(-90.0, float(m.group(1)))
            out.append((t, v))
    return out

def motion_energy(path):
    """Scene-change score per frame at 4fps -> list of (t, score)."""
    r = subprocess.run(
        ["ffmpeg", "-v", "quiet", "-i", path,
         "-vf", "fps=4,scale=160:-2,select='gte(scene,0)',"
                "metadata=print:key=lavfi.scene_score:file=-",
         "-f", "null", "-"], capture_output=True, text=True)
    out = []
    t = None
    for line in r.stdout.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1)); continue
        m = re.search(r"scene_score=([\d.]+)", line)
        if m and t is not None:
            out.append((t, float(m.group(1))))
    return out

def norm_series(series):
    if not series:
        return []
    vals = [v for _, v in series]
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-6:
        return [(t, 0.5) for t, _ in series]
    return [(t, (v - lo) / (hi - lo)) for t, v in series]

def window_mean(series, start, end):
    vals = [v for t, v in series if start <= t < end]
    return sum(vals) / len(vals) if vals else 0.0

def best_window(path, dur, has_audio):
    aud = norm_series(audio_energy(path)) if has_audio else []
    mot = norm_series(motion_energy(path))
    best, best_score = 0.0, -1.0
    s = 0.0
    while s <= dur - CLIP:
        sc = 0.0
        if aud:
            sc += 0.6 * window_mean(aud, s, s + CLIP)
        sc += (0.4 if aud else 1.0) * window_mean(mot, s, s + CLIP)
        if sc > best_score:
            best_score, best = sc, s
        s += 0.5
    return best, best_score

items = json.load(open(os.path.join(SP, "metadata.json")))
videos = [it for it in items if it["type"] == "video"]
print(f"{len(videos)} videos")

clips = {}
for i, it in enumerate(videos):
    src = os.path.join(SRC, it["file"])
    base = os.path.splitext(it["file"])[0]
    out = os.path.join(DST, base + ".mp4")
    dur = it["duration"] or 10.0
    w, h, rot, has_audio = probe_stream(src)
    if w >= h:
        tw = min(w, 1920); th = int(tw * h / w) & ~1; tw &= ~1
    else:
        th = min(h, 1920); tw = int(th * w / h) & ~1; th &= ~1
    if dur <= CLIP + 0.6:
        start, t = 0.0, dur
        score = None
    else:
        start, score = best_window(src, dur, has_audio)
        t = CLIP
    clips[it["file"]] = {"start": round(start, 1), "len": round(t, 2),
                         "score": score, "out": base + ".mp4"}
    if os.path.exists(out) and os.path.getsize(out) > 100_000:
        print(f"[{i+1}/{len(videos)}] skip existing {base}")
        continue
    vf = f"scale_vt=w={tw}:h={th}:color_matrix=bt709:" \
         "color_primaries=bt709:color_transfer=bt709"
    if rot in TRANSPOSE:
        vf = f"transpose_vt=dir={TRANSPOSE[rot]}," + vf
    cmd = ["ffmpeg", "-y", "-v", "error", "-noautorotate",
           "-hwaccel", "videotoolbox", "-hwaccel_output_format", "videotoolbox_vld",
           "-ss", f"{start:.2f}", "-t", f"{t:.2f}", "-i", src,
           "-vf", vf, "-metadata:s:v", "rotate=0",
           "-c:v", "h264_videotoolbox", "-b:v", "5M",
           "-c:a", "aac", "-b:a", "128k", "-ac", "2",
           "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        # fallback: software decode+scale+tonemap-less bt709 convert
        cmd_sw = ["ffmpeg", "-y", "-v", "error",
                  "-ss", f"{start:.2f}", "-t", f"{t:.2f}", "-i", src,
                  "-vf", f"scale={tw}:{th},format=yuv420p",
                  "-c:v", "h264_videotoolbox", "-b:v", "5M",
                  "-c:a", "aac", "-b:a", "128k", "-ac", "2",
                  "-movflags", "+faststart", out]
        r2 = subprocess.run(cmd_sw, capture_output=True, text=True)
        tag = "sw-fallback" if r2.returncode == 0 else "FAILED"
        print(f"[{i+1}/{len(videos)}] {tag} {base}: {r.stderr.strip()[:200]}")
    else:
        print(f"[{i+1}/{len(videos)}] ok {base} start={start:.1f}s"
              + (f" score={score:.2f}" if score else " (whole clip)"))

json.dump(clips, open(os.path.join(SP, "clips.json"), "w"), indent=1)
print("wrote clips.json")
