#!/usr/bin/env python3
"""Extract timestamp + GPS from all media files, interpolate karen's locations,
cluster into location chapters. Output: metadata.json"""
import glob, json, os, re, subprocess, sys
from datetime import datetime, timezone

from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()

FOLDER = "/Volumes/SSK SSD/Applications/Alaska Cruise Timeline Ordered - Both Phones"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.json")

NAME_RE = re.compile(
    r"^(\d+)_(\d{4}-\d{2}-\d{2})_(\d{6})Z_(photo|video)_(gary|karen|wife)_(.+)$")


def dms_to_deg(dms, ref):
    deg = float(dms[0]) + float(dms[1]) / 60 + float(dms[2]) / 3600
    return -deg if ref in ("S", "W") else deg


def photo_gps(path):
    try:
        img = Image.open(path)
        gps = img.getexif().get_ifd(0x8825)
        img.close()
        if not gps:
            return None
        lat = gps.get(2)
        lon = gps.get(4)
        if not lat or not lon:
            return None
        return (dms_to_deg(lat, gps.get(1, "N")), dms_to_deg(lon, gps.get(3, "E")))
    except Exception as e:
        print(f"  warn: {os.path.basename(path)}: {e}", file=sys.stderr)
        return None


# Authoritative capture time from media internals (filenames are unreliable:
# karen's iCloud photo exports stamped local time as UTC; some video filenames
# drift from creation_time).
def date_offset_hours(date_str):
    # trip heuristic when a file lacks a tz offset: Alaska days AKDT, else PDT
    return -8 if "2026-06-01" <= date_str <= "2026-06-05" else -7

def photo_true_ts(path, person, fallback_ts, fallback_date):
    try:
        img = Image.open(path)
        ex = img.getexif()
        ifd = ex.get_ifd(0x8769)
        img.close()
        dto = ifd.get(36867) or ex.get(306)          # DateTimeOriginal / DateTime
        off = ifd.get(36881)                          # OffsetTimeOriginal
        if dto:
            dt = datetime.strptime(dto, "%Y:%m:%d %H:%M:%S")
            if off and re.match(r"[+-]\d{2}:\d{2}", off):
                h, m = int(off[:3]), int(off[0] + off[4:6])
                dt = dt.replace(tzinfo=timezone(timedelta(hours=h, minutes=m)))
            else:
                dt = dt.replace(tzinfo=timezone(timedelta(
                    hours=date_offset_hours(dt.strftime("%Y-%m-%d")))))
            return dt.timestamp()
    except Exception:
        pass
    # fallback: gary filenames are true UTC; karen's are local mislabeled UTC
    if person == "gary":
        return fallback_ts
    # local 10:34 stamped "10:34Z" at offset -7 -> true UTC is +7h
    return fallback_ts - date_offset_hours(fallback_date) * 3600

def video_true_ts(path, fallback_ts):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries",
         "format_tags=com.apple.quicktime.creationdate,creation_time",
         "-of", "default=noprint_wrappers=1:nokey=0", path],
        capture_output=True, text=True)
    tags = dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)
    cd = tags.get("TAG:com.apple.quicktime.creationdate")
    if cd:
        try:
            return datetime.strptime(cd, "%Y-%m-%dT%H:%M:%S%z").timestamp()
        except ValueError:
            pass
    ct = tags.get("TAG:creation_time")
    if ct:
        try:
            return datetime.fromisoformat(ct.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return fallback_ts

ISO6709_RE = re.compile(r"^([+-]\d+\.?\d*)([+-]\d+\.?\d*)")


def video_gps(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries",
         "format_tags=com.apple.quicktime.location.ISO6709",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    m = ISO6709_RE.match(r.stdout.strip())
    return (float(m.group(1)), float(m.group(2))) if m else None


def video_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


items = []
files = sorted(f for f in os.listdir(FOLDER)
               if not f.startswith(".") and f != "manifest.csv")
for name in files:
    m = NAME_RE.match(name)
    if not m:
        print(f"  skip unparseable: {name}", file=sys.stderr)
        continue
    seq, date, hms, mtype, person, orig = m.groups()
    fn_ts = datetime.strptime(f"{date}T{hms}Z", "%Y-%m-%dT%H%M%SZ").replace(
        tzinfo=timezone.utc).timestamp()
    path = os.path.join(FOLDER, name)
    if mtype == "photo":
        gps = photo_gps(path)
        ts = photo_true_ts(path, person, fn_ts, date)
        dur = None
    else:
        gps = video_gps(path)
        ts = video_true_ts(path, fn_ts)
        dur = video_duration(path)
    items.append({
        "seq": int(seq), "file": name, "ts": ts,
        "iso": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        "type": mtype, "person": person,
        "lat": gps[0] if gps else None, "lon": gps[1] if gps else None,
        "gps_source": "exif" if gps else None, "duration": dur,
    })

items.sort(key=lambda x: (x["ts"], x["seq"]))

# Interpolate missing GPS from nearest anchors in time
anchors = [(it["ts"], it["lat"], it["lon"]) for it in items if it["lat"] is not None]
print(f"{len(items)} items, {len(anchors)} GPS anchors")

for it in items:
    if it["lat"] is not None:
        continue
    t = it["ts"]
    before = [a for a in anchors if a[0] <= t]
    after = [a for a in anchors if a[0] >= t]
    if before and after:
        b, a = before[-1], after[0]
        if a[0] == b[0]:
            lat, lon = b[1], b[2]
        else:
            f = (t - b[0]) / (a[0] - b[0])
            lat = b[1] + f * (a[1] - b[1])
            lon = b[2] + f * (a[2] - b[2])
        it["gps_source"] = "interpolated"
    elif before:
        lat, lon = before[-1][1], before[-1][2]
        it["gps_source"] = "nearest"
    else:
        lat, lon = after[0][1], after[0][2]
        it["gps_source"] = "nearest"
    it["lat"], it["lon"] = round(lat, 5), round(lon, 5)

with open(OUT, "w") as f:
    json.dump(items, f, indent=1)
print(f"wrote {OUT}")

# Summary by day for review
from collections import Counter
days = Counter(it["iso"][:10] for it in items)
for d in sorted(days):
    day_items = [it for it in items if it["iso"][:10] == d]
    lats = [it["lat"] for it in day_items]
    lons = [it["lon"] for it in day_items]
    print(f"{d}: {len(day_items):3d} items  lat {min(lats):.2f}..{max(lats):.2f}"
          f"  lon {min(lons):.2f}..{max(lons):.2f}")
