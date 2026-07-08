#!/usr/bin/env python3
"""Assign each item a place using local calendar day + cruise itinerary,
refined by exif GPS anchors. Group consecutive same-place runs into chapters.
Applies overrides.json (place/skip/seq) from the site folder.
Output: chapters.json"""
import json, os
from datetime import datetime, timezone, timedelta

SP = os.path.dirname(os.path.abspath(__file__))
SITE = "/Volumes/SSK SSD/Applications/Alaska Cruise Slideshow Site"
items = json.load(open(os.path.join(SP, "metadata.json")))

overrides = {}
ov_path = os.path.join(SITE, "overrides.json")
if os.path.exists(ov_path):
    overrides = json.load(open(ov_path))
    print(f"loaded {len(overrides)} overrides")

# Local time on the trip: Vancouver/Seattle PDT (UTC-7), Alaska AKDT (UTC-8)
def local_dt(ts, lon):
    offset = -8 if lon < -130 else -7
    return datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=offset)))

# Itinerary: local calendar day -> place (or callable for split days)
# Jun 4 verified from media: Karen at Ketchikan dock 10 AM (exif -08:00),
# Gary GPS at Ketchikan 9:15 PM — full-day port call.
ITINERARY = {
    "2026-05-29": "Vancouver, British Columbia",
    "2026-05-30": "Vancouver, British Columbia",
    "2026-05-31": "At Sea — Inside Passage",
    "2026-06-01": "Juneau, Alaska",
    "2026-06-02": "Skagway, Alaska",
    "2026-06-03": "Glacier Bay, Alaska",
    "2026-06-04": "Ketchikan, Alaska",
    "2026-06-05": "At Sea — Inside Passage",
    "2026-06-06": "Marysville, Washington",
    "2026-06-07": "Whidbey Island, Washington",
    "2026-06-08": "Seattle, Washington",
}

kept = []
for it in items:
    ov = overrides.get(it["file"], {})
    if ov.get("skip"):
        continue
    ldt = local_dt(it["ts"], it["lon"])
    day = ldt.strftime("%Y-%m-%d")
    place = ITINERARY.get(day, "At Sea — Inside Passage")
    if callable(place):
        place = place(ldt)
    if "place" in ov:
        place = ov["place"]
    it["place"] = place
    it["local_iso"] = ldt.isoformat()
    it["friendly"] = ldt.strftime("%A, %B %-d — %-I:%M %p")
    it["sort"] = ov.get("seq", it["ts"])
    kept.append(it)

kept.sort(key=lambda x: (x["sort"], x["seq"]))

# Group consecutive same-place items into chapters
chapters = []
for it in kept:
    if chapters and chapters[-1]["place"] == it["place"]:
        chapters[-1]["items"].append(it)
    else:
        chapters.append({"place": it["place"], "items": [it]})

# Merge tiny at-sea chapters (<3 items) into the previous chapter;
# named ports always keep their own chapter (and map dot)
merged = []
for ch in chapters:
    if merged and len(ch["items"]) < 3 and ch["place"].startswith("At Sea"):
        merged[-1]["items"].extend(ch["items"])
    else:
        merged.append(ch)
chapters = merged

def date_range(items_):
    a = local_dt(items_[0]["ts"], items_[0]["lon"])
    b = local_dt(items_[-1]["ts"], items_[-1]["lon"])
    if a.date() == b.date():
        return a.strftime("%A, %B %-d")
    if a.month == b.month:
        return f"{a.strftime('%B %-d')} – {b.day}"
    return f"{a.strftime('%B %-d')} – {b.strftime('%B %-d')}"

for i, ch in enumerate(chapters):
    its = ch["items"]
    ch["index"] = i
    # map dot: prefer real GPS anchors within the chapter
    anchors = [x for x in its if x["gps_source"] == "exif"]
    pool = anchors if anchors else its
    ch["lat"] = round(sum(x["lat"] for x in pool) / len(pool), 4)
    ch["lon"] = round(sum(x["lon"] for x in pool) / len(pool), 4)
    ch["date_friendly"] = date_range(its)
    n_p = sum(1 for x in its if x["type"] == "photo")
    n_v = len(its) - n_p
    ch["dur_s"] = n_p * 3 + n_v * 10
    print(f"{i:2d}. {ch['place']:32s} {ch['date_friendly']:22s} "
          f"{n_p:3d}p {n_v:2d}v  {ch['dur_s']//60}:{ch['dur_s']%60:02d}")

# At-sea dots: midpoint of the leg between neighboring stops, so they
# read as "en route" rather than piling onto an anchor
for i, ch in enumerate(chapters):
    if ch["place"].startswith("At Sea") and 0 < i < len(chapters) - 1:
        ch["lat"] = round((chapters[i-1]["lat"] + chapters[i+1]["lat"]) / 2, 4)
        ch["lon"] = round((chapters[i-1]["lon"] + chapters[i+1]["lon"]) / 2, 4)

total = sum(c["dur_s"] for c in chapters)
print(f"\nslideshow media total: {total//60}:{total%60:02d}, {len(kept)} items")
json.dump(chapters, open(os.path.join(SP, "chapters.json"), "w"), indent=1)
print("wrote chapters.json")
