# App Idea: AI-Driven Slideshow Creation Service

*Captured 2026-07-04 while building the Alaska Cruise slideshow. Revisit after current features are done.*

## The pitch
Upload your vacation photo/video dump (multiple phones, messy timestamps, no organization) and get back a cinematic, editable slideshow: journey map with animated route, location chapters, smart-trimmed video clips, music, Ken Burns motion — with dead-simple drag/trim/delete editing on top. "iMovie result, zero iMovie effort."

## What this project already proved works
- **Metadata intelligence**: authoritative timestamps from EXIF/QuickTime internals (filenames lie — iCloud exports stamp local time as UTC); timezone repair; GPS from anchored devices interpolated to non-GPS media; day+itinerary clustering into location chapters.
- **AI vision pass**: cheap model verifies photos match their assigned location (caught real mislabels).
- **Smart clip selection**: audio-energy + motion scoring finds the interesting 10 seconds automatically.
- **Journey map storytelling**: auto-built route map, dot-drop + camera-glide between chapters.
- **In-browser editing**: drag reorder, chapter moves, video trim with preview, delete/restore — all no-install, saved locally, exportable.
- **HDR video pipeline**: VideoToolbox tonemapping so iPhone HDR doesn't look washed out on the web.
- **Music**: local files with ducking under video audio, or Spotify (Premium, Web Playback SDK).

## Possible shapes
- **Mobile web app** (PWA): phone photos are already there; server does the pipeline; share link output.
- **SaaS**: upload → processing pipeline (the Python/ffmpeg steps generalize almost as-is) → hosted private slideshow link for family.
- **Mac app**: local-first, no upload of 100 GB — the pipeline already runs great locally.

## Open questions
- Storage/bandwidth economics for video-heavy uploads (this one trip = 15 GB raw).
- Music licensing for shareable outputs (Spotify only works per-viewer; local files can't be redistributed).
- Differentiation vs Google Photos/Apple Memories: the *journey map narrative*, timestamp repair across devices, and real editing control are the wedge.
- Privacy posture: family media is sensitive; local-first or private-by-default hosting.

## Feature idea: AI playlist suggestions (added 2026-07-05)
Ask user for genre preferences; gather context clues from photos and metadata
(locations, season, trip type, activities seen by vision, chapter energy);
LLM curates an upbeat track list matched to the show's arc; build the playlist
in the user's Spotify account via Search + playlist-create APIs (Spotify's own
Recommendations API is deprecated for new apps — LLM curation is the path).
Chapter-aware energy sequencing is the differentiator.

## Nearest next experiments (when revisited)
1. Generalize the pipeline scripts (config in, slideshow out) — they're currently trip-specific in ~5 places.
2. Try it on a second trip's dump end-to-end to find hardcoded assumptions.
3. Mock the mobile upload → link flow.
