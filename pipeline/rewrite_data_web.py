#!/usr/bin/env python3
"""Rewrite data.js to point at the pre-trimmed media/videos_web/ clips.

Each video file now *is* its trimmed window, so start becomes 0 and fullDur
collapses to the clip length. Idempotent. Preserves the file wrapper/format."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(ROOT, "data.js")
raw = open(path).read()
i, j = raw.index("{"), raw.rindex("}") + 1
d = json.loads(raw[i:j])

n = 0
def walk(o):
    global n
    if isinstance(o, dict):
        if o.get("type") == "video":
            o["src"] = o["src"].replace("media/videos_full/", "media/videos_web/")
            length = float(o["trim"]["len"])
            o["trim"]["start"] = 0.0
            o["fullDur"] = length
            n += 1
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)

walk(d)
open(path, "w").write(raw[:i] + json.dumps(d, ensure_ascii=True) + raw[j:])
print(f"rewrote {n} video slides -> videos_web (start=0)")
