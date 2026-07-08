# Alaska Cruise Slideshow — Complete Technical Documentation

*Written July 5, 2026. Everything needed to rebuild this project from scratch, plus
product notes at the end.*

---

## 1. What this is

A self-contained slideshow **website** (no build tools, no frameworks) that plays a
~28-minute cinematic show from a vacation media dump: animated journey map with
dot-drops and camera glides between location chapters, Ken Burns photos with
crossfades, smart-trimmed video clips with natural audio, date/location overlays,
music (local files or Spotify), and a full in-browser editor (reorder, move, trim,
delete). Built July 2026 from the "Alaska Cruise Timeline Ordered - Both Phones"
folder (375 files from two iPhones).

**Layout on disk (this folder):**

```
Alaska Cruise Slideshow Site/
├── index.html              # the entire app: styles + markup + logic (~1500 lines)
├── data.js                 # generated show data (chapters/slides/map) — see §5
├── serve.py                # local web server WITH HTTP Range support (§6.1)
├── Start Slideshow.command # double-click launcher (server + browser)
├── overrides.json          # per-file pipeline corrections (skip/place/seq)
├── media/
│   ├── photos/             # 292 web JPEGs (1920px, q82)
│   ├── videos_full/        # 83 full-length H.264 MP4s (tonemapped, rotated)
│   ├── vthumbs/            # 320px JPEG thumb per video (editor + blur backdrop)
│   └── map.jpg             # stitched basemap 4096×5120 (CARTO voyager z7)
├── pipeline/               # all build scripts + intermediate JSON (§3–4)
├── DOCUMENTATION.md        # this file
└── appidea.md              # product concept notes
```

---

## 2. Source data & the hard lessons

Input: one folder of photos (HEIC/JPEG) and videos (MOV), filenames like
`0466_2026-06-06_212317Z_video_gary_IMG_2645.MOV`
(`seq_date_timeZ_type_person_original`).

**Lesson 1 — filename timestamps lie.** Karen's iCloud web exports stamped her
*local wall time* as if it were UTC (photo EXIF said `10:34:22 -07:00`, filename
said `103422Z`) → everything of hers sorted 7–8h early. Some of Gary's *video*
filenames also drifted hours from truth. **Rule: only trust media internals** —
EXIF `DateTimeOriginal` + `OffsetTimeOriginal` (photos), QuickTime
`com.apple.quicktime.creationdate` (has tz offset; videos). Fallbacks: video
`creation_time` (UTC), then filename (treated as local for the iCloud-export
person, UTC otherwise).

**Lesson 2 — GPS is asymmetric.** Gary's media had EXIF GPS / QuickTime ISO6709
(62 anchors); Karen's iCloud exports were location-stripped. Fix: interpolate her
positions linearly in time between his anchors (they traveled together).

**Lesson 3 — a stale manifest.csv existed in the source folder** (639 rows vs 375
files). Folder contents are the only truth.

**Lesson 4 — one video (`0466...IMG_2645.MOV`) had wrong rotation metadata**
(claimed -90°, pixels were landscape). Kept an `IGNORE_ROTATION` exception list in
the transcoder.

**Duplicates:** the two-phone merge included byte-identical dupes and variant twins
(slo-mo `_1` renders, edited `IMG_E####`, re-saved `-1` trims). Detected by same
original-name/timestamp + md5; skipped via `overrides.json` (reversible).

---

## 3. The pipeline (pipeline/, run in this order)

Python venv with `pillow` + `pillow-heif`; system `ffmpeg` (needs `scale_vt` /
`transpose_vt` → ffmpeg 8+, macOS VideoToolbox) and `sips` (macOS built-in).

### 3.1 `extract_metadata.py` → `metadata.json`
Per file: authoritative UTC timestamp (§2 rules), GPS (photos: EXIF GPS IFD
0x8825 DMS→decimal; videos: ffprobe ISO6709 tag regex), video duration. Then GPS
interpolation for anchor-less items. Trip tz heuristic when offset missing:
Alaska days (Jun 1–5) = UTC-8, else UTC-7.

### 3.2 `cluster_chapters.py` → `chapters.json`
**Day + itinerary clustering** (NOT GPS-box matching — interpolated coords smear
across overnight sailings and mislabel things). Each item's *local calendar day*
(offset by longitude: < -130° → -8 else -7) maps through a hard-coded itinerary
(Vancouver May 29–30, At Sea May 31, Juneau Jun 1, Skagway Jun 2, Glacier Bay
Jun 3, Ketchikan Jun 4 *full day — verified from media*, At Sea Jun 5, Marysville
Jun 6, Whidbey Island Jun 7, Seattle Jun 8). Consecutive same-place runs become
chapters; tiny at-sea runs merge into the previous chapter but **named ports always
keep their chapter** (and map dot). Chapter dot = mean of real GPS anchors in it;
**at-sea chapter dots = midpoint of neighboring stops** (else they pile onto an
anchor). Applies `overrides.json`: `{file: {skip: true | place: "…" | seq: n}}`.

### 3.3 `build_map.py` → `media/map.jpg` + `map.json`
Web-mercator tile math at z=7. Tile range derived **from the chapter points**
(min/max tile ±1 margin — hard assert every point lands in-bounds; v1 cropped
Skagway off the top). Tiles: CARTO `voyager_nolabels` @2x (512px), OSM fallback,
0.15s delay, User-Agent set, local tile cache. Output `map.json`: image dims,
zoom, origin tile, attribution, and per-chapter pixel coords.

### 3.4 Photos: `convert_photos.sh`
`sips -s format jpeg -s formatOptions 82 --resampleHeightWidthMax 1920` per photo.

### 3.5 Videos: `transcode_full.py` → `media/videos_full/`
Full-length transcode (full length is what makes in-page trimming possible):
- **HDR→SDR**: iPhone HEVC is 10-bit HLG/BT.2020; naive transcode looks washed
  out. Hardware path: `-hwaccel videotoolbox -hwaccel_output_format
  videotoolbox_vld` + `scale_vt=w=W:h=H:color_matrix=bt709:color_primaries=bt709:
  color_transfer=bt709` (VTPixelTransferSession does proper tonemapping).
- **Rotation**: autorotate does NOT apply on the hw path — insert
  `transpose_vt=dir=` (rot 270→`clock`, 90→`cclock`, 180→`reversal`), plus
  `-noautorotate` and `-metadata:s:v rotate=0`. Respect `IGNORE_ROTATION`.
- Encode: `h264_videotoolbox -b:v 5M`, AAC 128k stereo, `+faststart`, long edge
  ≤1920.
- Thumbs: 1 frame @t=1s, 320px JPEG each → `media/vthumbs/`.

### 3.6 `process_videos.py` → `clips.json` (default trim windows)
"Most interesting 10s" per video: audio RMS per 0.5s (ffmpeg `astats` metadata) +
motion (scene scores at 4fps, 160px). Both min-max normalized per video; window
score = 0.6·audio + 0.4·motion (motion-only if no audio track); slide a 10s window
at 0.5s steps, keep the max. Videos ≤10.6s use their whole length.

### 3.7 `build_data.py` → `data.js`
Merges chapters+clips+map into `const DATA = {...}`. Also picks the intro hero
image (middle photo of the Glacier Bay chapter). **Bump the `data.js?v=N` query
in index.html every rebuild** — browsers cache aggressively.

---

## 4. The web app (index.html)

Zero dependencies. Sections below map to labeled comment blocks in the file.

### 4.1 Show flow
Intro card (hero photo, names/anniversary line, Begin button — the click is the
user gesture that unlocks audio) → for each chapter: **map sequence** → slides →
repeat → outro card ("The End", family names) → 6s fade to black. **Loop mode**:
after the blackout, reset dots/route/outro/music volume behind black, fade back
in 1.5s, restart at chapter 0.

**Map sequence**: chapter 0 = fit whole route (bounding box of points + padding),
dot drops (springy scale/translate keyframes), zoom to `CHAPTER_ZOOM=3.2×` fit
scale. Later chapters = **no zoom-out**: stay zoomed, extend the dashed route
path, glide (translate at constant zoom) to the next dot — pan duration scales
with pixel distance (clamp 1.1–2.8s) — then drop the dot. The map is one big
`<img>` + same-size SVG overlay (route path, dots, labels) inside a
`transform-origin:0 0` container; camera = translate+scale of that container.

**Slides**: two stacked `.layer` divs, double-buffered crossfade (0.8s opacity).
Each layer = blurred cover background (`blur(28px) brightness(.45)`; photos use
the photo, videos use their vthumb — fills letterbox bars) + `object-fit:contain`
media. Photos: 3s, Ken Burns via 4 alternating keyframe animations, duration =
slide time + both fades, scaled by playback speed. Videos: seek to trim start
(`currentTime`), play, end on `timeupdate ≥ start+len` (plus `ended` and a
speed-aware timeout guard). Location overlay (gold date + big place name,
bottom-left) fades in only on chapter change, ~4.5s.

### 4.2 Timing/pause/skip plumbing
`wait(ms)` sleeps in 100ms nominal steps: each step awaits un-pause, divides by
`SPEED`, and aborts when `skipTo` (chapter jump) or `slideJump` (slide jump) is
set. Chapter skips accumulate (`skipTo = (skipTo ?? chIdx) + d`); slide skips
accumulate similarly. Pause = boolean + waiter list; also pauses `<video>`s and
music/Spotify. Speed (0.5/1/1.5/2×) scales waits, Ken Burns duration and video
`playbackRate` (pitch preserved by browser); music playback rate is untouched.

### 4.3 Control bar
Auto-hides after 3s idle, shows on mousemove, pinned while paused. Contents:
chapter label + position, ⏮ ◀◀ ▶/⏸ ▶▶ ⏭, speed pills, loop toggle (persisted),
fullscreen toggle, ✎ edit, 🎵 music, mute. All icons inline SVG (emoji glyphs
render as boxes in some contexts — learned the hard way with the pause icon).
Keyboard: Space pause, ←/→ chapters, M mute, F fullscreen, L loop, D debug,
E editor, Esc closes modals. Global keys are disabled while the editor or trim
modal is open.

### 4.4 Debug overlay (D)
Monospace panel: filename / taken (local, human) / chapter + slide no. / GPS
source (exif|interpolated|nearest), plus a copy-to-clipboard button (flashes a
checkmark; textarea execCommand fallback). This is the user's mechanism for
reporting misplaced items.

### 4.5 Edit mode (E / ✎)
Full-screen overlay. Chapters as sections of drag-reorderable thumbnails
(photos: the media JPEG; videos: vthumb + duration badge + ✂ button — **never**
`<video>` thumbnails: 78 of them starve the browser's per-host connection pool
and block everything else). Drag within/between sections (HTML5 DnD, insertion
point by midpoint); on drop the **entire order is rewritten** (deterministic:
`order[file] = chapterIdx*100000 + i*10`, `chapter[file] = chapterIdx`). ✕
removes an item into a "Removed from show" section (click to restore).
**Selection highlight** (yellow outline): click selects; survives drags, trim
saves, and re-renders; deleting the selected item passes the highlight to the
next item in that chapter; opening the editor mid-show auto-selects the slide
that was playing; auto-scrolled into view.

**Trim editor**: filmstrip strip (9 frames drawn to canvas by seeking a hidden
helper video) + golden selection window with draggable left/right edge handles
(live-scrubs the preview to the exact frame) and draggable middle (slides the
window, length preserved) + click-to-peek + white playhead. Min 1s, max = full
video. Preview plays only the window — playback is hard-clamped by persistent
`timeupdate`/`play` listeners (can't escape the selection).

**Persistence**: all edits in `localStorage.slideEdits` =
`{order:{file:key}, chapter:{file:ci}, trim:{file:{start,len}}, skip:{file:true}}`.
`buildShow()` merges them over `DATA` into the runtime `SHOW` structure at load
and after each editor change (order changes take effect at the next chapter;
trims apply immediately, looked up live at video start). "Export changes"
downloads `edits.json` — same shape — which can be baked permanently via the
pipeline (map to overrides/data). "Reset all edits" clears.

### 4.6 Music
Source toggle: **Local files** or **Spotify** (persisted).

*Local*: tracks stored as blobs in IndexedDB (`slideshow-music/tracks`,
autoincrement id + order). Panel: add via picker or drag-drop, reorder ▲▼,
remove ✕, volume slider, on/off, playing indicator. Playback chains tracks,
loops the playlist, starts on Begin, pauses with the show, **ducks to 15% with a
900ms ramp during videos** (un-duck skipped between consecutive videos), fades
out over the final blackout, obeys mute.

*Spotify*: Web Playback SDK (full tracks, **Premium required**). OAuth PKCE
entirely in-browser: SHA-256 challenge, redirect to accounts.spotify.com, code
exchange + refresh-token persistence in localStorage. **Redirect URI must be
`http://127.0.0.1:8471/`** — Spotify forbids `localhost` and `file://`; this is
why the launcher exists and why 127.0.0.1 is the canonical origin (localStorage —
music, edits, tokens — is per-origin!). Player = `new Spotify.Player(...)` with
`getOAuthToken` callback; on `ready`, PUT `/v1/me/player/play?device_id=` with
`context_uri: spotify:playlist:ID` (parsed from a pasted share link). Ducking/
fades via stepped `player.setVolume()` ramps — same envelope as local. Panel
fields: Client ID (default baked in), playlist link, Connect button, status line.
Graceful offline degradation at every step.

### 4.7 Serving — critical gotcha
`python3 -m http.server` **does not support HTTP Range requests** → browsers
report videos unseekable → every seek lands at 0:00 → trims silently don't work.
`serve.py` implements single-range 206 responses (start/suffix ranges, 416 on
bad ranges) on ThreadingHTTPServer, bound to 127.0.0.1:8471. The launcher starts
it if the port is free, then opens the browser. (Opening `index.html` via
`file://` also plays fine — but Spotify won't work there, and it's a different
localStorage origin.)

---

## 5. Data schemas

```js
// data.js
DATA = {
  title, dates, hero,                     // intro
  map: { width, height, zoom, tile_x0, tile_y0, tile_px, attribution,
         points: [{chapter, place, lat, lon, x, y}] },   // px in map.jpg space
  chapters: [{ place, date, lat, lon, slides: [
    { src, type: "photo"|"video", dur,     // dur = display seconds
      file, t, src_gps,                    // debug: filename, taken, gps source
      trim: {start, len}, fullDur          // videos only
    }]}]
}
// localStorage.slideEdits / exported edits.json — see §4.5
// overrides.json (pipeline-side): { "<filename>": {skip|place|seq} }
```

---

## 6. Rebuild runbook

```bash
python3 -m venv venv && venv/bin/pip install pillow pillow-heif
venv/bin/python pipeline/extract_metadata.py     # → metadata.json
venv/bin/python pipeline/cluster_chapters.py     # → chapters.json (uses overrides.json)
venv/bin/python pipeline/build_map.py            # → media/map.jpg + map.json
zsh    pipeline/convert_photos.sh                # → media/photos/
venv/bin/python pipeline/process_videos.py       # → clips.json (default trims)
venv/bin/python pipeline/transcode_full.py       # → media/videos_full/
# vthumbs: ffmpeg -ss 1 -frames:v 1 -vf scale=320:-2 per video → media/vthumbs/
venv/bin/python pipeline/build_data.py           # → data.js  (bump ?v= in index.html!)
./Start\ Slideshow.command
```

Paths at the top of each script point at the source folder and this site folder —
those are the only things to change for a different trip. `cluster_chapters.py`'s
itinerary table is the one genuinely trip-specific block.

---

## 7. Product notes — "Slideshow Studio" (monetizable version)

Target flow (Gary's spec): *user provides an intro slide, chapter graphics, and a
closing slide, adds photos and videos, submits; gets our pipeline result; uses the
edit features we built; final edit → save → either export (no music) or we host
their slideshow with a Spotify-music option (Premium required).*

### What generalizes almost as-is
- The entire pipeline (§3): only the source path and the itinerary table are
  trip-specific. Ports/itinerary can be **inferred** (cluster GPS anchors + a
  reverse-geocoding call) or collected in onboarding ("where did you go, roughly
  what days?").
- The whole player + editor (§4): already data-driven from `data.js` + edits.
- The edits.json round-trip is exactly the save/export model: user edits in
  browser → server bakes → final asset.

### The user flow, productized
1. **Onboarding wizard**: trip name/dates → upload media (phone-first PWA;
   directory upload on desktop) → optional: pick intro/chapter/closing templates
   (title cards are just HTML — offer themes, fonts, color palettes, hero photo
   pick) → submit.
2. **Processing service**: the pipeline as a job queue (per-job ffmpeg workers;
   Apple-silicon runners or libx264+zscale tonemap on Linux). Progress page with
   the day-by-day clustering shown live for early delight.
3. **Review & edit**: our editor verbatim + a "runtime budget" readout; server-
   side persistence of edits (replace localStorage with account storage).
4. **Finalize**: save → (a) **Export**: server renders a real MP4 (headless
   chromium capture, or ffmpeg composition from data.js — deterministic and
   cheaper) — *no licensed music* in exports; (b) **Hosted**: private share link
   on our domain, viewer streams our player; **Spotify Connect** button lets any
   Premium viewer attach their own account for music (licensing-clean because
   playback is per-viewer through Spotify's SDK).

### Enhancements to consider
- **Music**: license a royalty-free library for exports (the gap in the current
  model); auto-beat-matched slide timing as a premium feature.
- **AI playlist builder (Spotify)**: ask the user's genres/decades/explicit
  filter, combine with context we already extract (locations, season, trip type,
  vision-detected activities, chapter durations/energy), have an LLM curate a
  concrete track list, then resolve via Spotify **Search** and create the
  playlist in the user's own account (`playlist-modify-private` scope).
  NOTE: Spotify's Recommendations/Audio-Features APIs are deprecated for new
  apps — LLM curation + Search is the viable (and more differentiated) path.
  Chapter-aware sequencing: match energy to chapters (upbeat ports, sweeping
  glacier day, celebratory finale) and sequence track lengths so transitions
  land near chapter boundaries. Playlist lives in the user's account →
  licensing-clean playback through the existing Premium player. For exports,
  map the same mood/tempo tags to the licensed library.
- **AI upgrades**: vision captioning for overlays ("Whale watching, Auke Bay");
  auto-highlight detection beyond audio/motion (faces, smiles, animals); face
  grouping ("more of Noelle"); dedupe/quality-cull suggestions; auto-narrative
  intro text; text-to-speech narration.
- **Multi-contributor merge** is the moat: N phones, mixed timezones, stripped
  GPS — our timestamp-repair + anchor-interpolation already solves what Google/
  Apple memories don't. Market it ("everyone AirDrops/uploads, we untangle it").
- **Map themes** (watercolor, dark, satellite) and non-travel fallbacks (no GPS →
  timeline "chapters by day/event" instead of map).
- **Mobile PWA** viewer + editor (thumb drag works on touch; trim handles already
  pointer-event based).
- **Sharing/permissions**: private links, expiry, download-disabled preview,
  family co-editing.
- **Monetization**: free tier (watermark, 5-min cap, 720p export) → one-time per
  slideshow ($15–30, matches "special occasion" willingness) → subscription for
  hosting/storage; upsells: 4K export, extra storage years, physical keepsake
  (QR-linked card).
- **Cost watch-outs**: storage/egress for video-heavy trips (this one: 15 GB raw,
  3.6 GB processed); transcode compute; keep originals only during processing,
  retain processed only.
- **Privacy**: family media — encrypt at rest, private by default, clear retention,
  easy full-delete. This is a trust product.
