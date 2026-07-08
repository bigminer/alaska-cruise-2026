#!/bin/zsh
# Convert all photos to web-sized JPEG via sips
SRC="/Volumes/SSK SSD/Applications/Alaska Cruise Timeline Ordered - Both Phones"
DST="/Volumes/SSK SSD/Applications/Alaska Cruise Slideshow Site/media/photos"
mkdir -p "$DST"
count=0; fail=0
for f in "$SRC"/*_photo_*; do
  base="${f:t:r}"
  out="$DST/$base.jpg"
  [[ -f "$out" ]] && { ((count++)); continue; }
  if sips -s format jpeg -s formatOptions 82 --resampleHeightWidthMax 1920 "$f" --out "$out" >/dev/null 2>&1; then
    ((count++))
  else
    ((fail++)); echo "FAIL: $base"
  fi
done
echo "converted=$count failed=$fail"
