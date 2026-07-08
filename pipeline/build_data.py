#!/usr/bin/env python3
"""Merge chapters.json + clips.json + map.json into the site's data.js."""
import json, os

SP = os.path.dirname(os.path.abspath(__file__))
SITE = "/Volumes/SSK SSD/Applications/Alaska Cruise Slideshow Site"

chapters = json.load(open(os.path.join(SP, "chapters.json")))
clips = json.load(open(os.path.join(SP, "clips.json")))
mapdata = json.load(open(os.path.join(SP, "map.json")))

missing = []
out_chapters = []
for ch in chapters:
    slides = []
    for it in ch["items"]:
        base = os.path.splitext(it["file"])[0]
        trim = None
        full_dur = None
        if it["type"] == "photo":
            src = f"media/photos/{base}.jpg"
            dur = 3.0
        else:
            c = clips.get(it["file"])
            src = f"media/videos_full/{base}.mp4"
            dur = c["len"] if c else 10.0
            trim = {"start": c["start"] if c else 0.0, "len": round(dur, 2)}
            full_dur = round(it.get("duration") or dur, 2)
        if not src or not os.path.exists(os.path.join(SITE, src)):
            missing.append(it["file"])
            continue
        slide = {"src": src, "type": it["type"], "dur": round(dur, 2),
                 "file": it["file"], "t": it["friendly"],
                 "src_gps": it["gps_source"]}
        if trim:
            slide["trim"] = trim
            slide["fullDur"] = full_dur
        slides.append(slide)
    out_chapters.append({
        "place": ch["place"],
        "date": ch["date_friendly"],
        "lat": ch["lat"], "lon": ch["lon"],
        "slides": slides,
    })

# hero image for intro: middle photo of Glacier Bay chapter
hero = None
for ch, oc in zip(chapters, out_chapters):
    if "Glacier Bay" in ch["place"]:
        photos = [s for s in oc["slides"] if s["type"] == "photo"]
        if photos:
            hero = photos[len(photos) // 2]["src"]
        break

data = {
    "title": "Alaska Cruise 2026",
    "dates": "May 29 – June 8, 2026",
    "hero": hero,
    "map": mapdata,
    "chapters": out_chapters,
}
with open(os.path.join(SITE, "data.js"), "w") as f:
    f.write("const DATA = " + json.dumps(data) + ";\n")

n = sum(len(c["slides"]) for c in out_chapters)
print(f"data.js written: {len(out_chapters)} chapters, {n} slides, hero={hero}")
if missing:
    print(f"MISSING {len(missing)}:", *missing[:10], sep="\n  ")
