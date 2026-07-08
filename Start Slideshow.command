#!/bin/zsh
# Double-click to start the Alaska Cruise slideshow.
# Serves the site on http://127.0.0.1:8471 (required for Spotify) and opens it.
cd "$(dirname "$0")"
if ! lsof -nP -iTCP:8471 -sTCP:LISTEN >/dev/null 2>&1; then
  nohup python3 serve.py >/dev/null 2>&1 &
  sleep 0.7
fi
open "http://127.0.0.1:8471/"
