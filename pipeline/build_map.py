#!/usr/bin/env python3
"""
Build Alaska cruise map: download tiles, stitch them, and compute pixel coordinates.
"""
import json
import math
import os
import time
import urllib.request
from pathlib import Path
from PIL import Image

# Configuration
ZOOM = 7
LAT_MIN, LAT_MAX = 46.8, 60.2
LON_MIN, LON_MAX = -137.8, -121.3
TILE_SOURCES = [
    ("https://a.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}@2x.png", 512),
    ("https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png", 512),
    ("https://tile.openstreetmap.org/{z}/{x}/{y}.png", 256),
]
TILE_CACHE_DIR = Path("/private/tmp/claude-501/-Users-gary-Dev/59bbb002-7372-4dc1-8759-745ca5bb7bef/scratchpad/tiles")
USER_AGENT = "AlaskaCruiseSlideshow/1.0 (personal project)"
REQUEST_DELAY = 0.15

OUTPUT_MAP = Path("/Volumes/SSK SSD/Applications/Alaska Cruise Slideshow Site/media/map.jpg")
OUTPUT_MAP_JSON = Path("/private/tmp/claude-501/-Users-gary-Dev/59bbb002-7372-4dc1-8759-745ca5bb7bef/scratchpad/map.json")
OUTPUT_CHECK = Path("/private/tmp/claude-501/-Users-gary-Dev/59bbb002-7372-4dc1-8759-745ca5bb7bef/scratchpad/map_check.jpg")
CHAPTERS_FILE = Path("/private/tmp/claude-501/-Users-gary-Dev/59bbb002-7372-4dc1-8759-745ca5bb7bef/scratchpad/chapters.json")

# Ensure output directory exists
OUTPUT_MAP.parent.mkdir(parents=True, exist_ok=True)
TILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def lat_lon_to_tile(lat, lon, z):
    """Convert lat/lon to tile coordinates at zoom level z."""
    n = 2.0 ** z
    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def tile_to_pixel(tile_x, tile_y, tile_x0, tile_y0, tile_px):
    """Convert tile coordinates to pixel coordinates in the stitched image."""
    px_x = (tile_x - tile_x0) * tile_px
    px_y = (tile_y - tile_y0) * tile_px
    return int(round(px_x)), int(round(px_y))


def download_tile(z, x, y):
    """Download a tile from the first available source, with fallback. Returns (image, tile_px)."""
    cache_path = TILE_CACHE_DIR / f"{z}_{x}_{y}.png"

    # Check which source was used for this tile (stored in metadata file)
    meta_path = TILE_CACHE_DIR / f"{z}_{x}_{y}.meta"
    if cache_path.exists() and meta_path.exists():
        with open(meta_path) as f:
            tile_px = int(f.read().strip())
        return Image.open(cache_path), tile_px

    for url_template, tile_px in TILE_SOURCES:
        url = url_template.format(z=z, x=int(x), y=int(y))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read()
            img = Image.open(__import__("io").BytesIO(data))
            img.save(cache_path)
            with open(meta_path, "w") as f:
                f.write(str(tile_px))
            return img, tile_px
        except Exception as e:
            print(f"Failed to download {url}: {e}")
            continue

    raise RuntimeError(f"Failed to download tile z={z}, x={int(x)}, y={int(y)}")


def main():
    # Load chapters first — the points are the source of truth for coverage.
    with open(CHAPTERS_FILE) as f:
        chapters = json.load(f)

    # Tile coords of every chapter point at z=7
    pt_tiles = [lat_lon_to_tile(ch["lat"], ch["lon"], ZOOM) for ch in chapters]
    pt_tx = [t[0] for t in pt_tiles]
    pt_ty = [t[1] for t in pt_tiles]

    # Min/max tile INCLUSIVE, plus 1 extra tile of margin on every side.
    n_tiles = 2 ** ZOOM
    tile_x0 = max(0, int(math.floor(min(pt_tx))) - 1)
    tile_x1 = min(n_tiles, int(math.floor(max(pt_tx))) + 2)  # exclusive end: max tile + 1 margin + 1
    tile_y0 = max(0, int(math.floor(min(pt_ty))) - 1)
    tile_y1 = min(n_tiles, int(math.floor(max(pt_ty))) + 2)

    print(f"Building map for zoom={ZOOM}, tile range derived from {len(chapters)} chapter points")
    print(f"Tile range: x={tile_x0}-{tile_x1}, y={tile_y0}-{tile_y1}")

    # Download and stitch tiles
    tiles_downloaded = 0
    tile_px = None
    images = []

    for ty in range(tile_y0, tile_y1):
        row = []
        for tx in range(tile_x0, tile_x1):
            print(f"  Downloading tile {tx},{ty}...", end=" ", flush=True)
            img, tp = download_tile(ZOOM, tx, ty)
            if tile_px is None:
                tile_px = tp
            row.append(img)
            tiles_downloaded += 1
            print("ok")
            time.sleep(REQUEST_DELAY)
        images.append(row)

    print(f"Downloaded {tiles_downloaded} tiles, tile_px={tile_px}")

    # Stitch tiles into single image
    img_width = (tile_x1 - tile_x0) * tile_px
    img_height = (tile_y1 - tile_y0) * tile_px
    stitched = Image.new("RGB", (img_width, img_height))

    for row_idx, row in enumerate(images):
        for col_idx, tile_img in enumerate(row):
            x = col_idx * tile_px
            y = row_idx * tile_px
            stitched.paste(tile_img, (x, y))

    print(f"Stitched image: {stitched.size[0]}x{stitched.size[1]}")

    # Compute pixel coordinates for every chapter
    points = []
    for ch in chapters:
        tile_x, tile_y = lat_lon_to_tile(ch["lat"], ch["lon"], ZOOM)
        px_x, px_y = tile_to_pixel(tile_x, tile_y, tile_x0, tile_y0, tile_px)

        # HARD ASSERT: every point must fall inside the stitched image
        assert 0 <= px_x < img_width and 0 <= px_y < img_height, (
            f"Chapter {ch['index']} '{ch['place']}' out of bounds: "
            f"({px_x}, {px_y}) vs image {img_width}x{img_height}"
        )

        points.append({
            "chapter": ch["index"],
            "place": ch["place"],
            "lat": ch["lat"],
            "lon": ch["lon"],
            "x": px_x,
            "y": px_y,
        })
        print(f"  Chapter {ch['index']:2d}: {ch['place']:30s} -> ({px_x:4d}, {px_y:4d})")

    # Save map.jpg
    stitched.save(OUTPUT_MAP, "JPEG", quality=85)
    print(f"Saved map: {OUTPUT_MAP}")

    # Save map.json
    # Determine attribution based on actual source used
    attribution = "© OpenStreetMap contributors © CARTO"

    map_data = {
        "width": img_width,
        "height": img_height,
        "zoom": ZOOM,
        "tile_x0": tile_x0,
        "tile_y0": tile_y0,
        "tile_px": tile_px,
        "attribution": attribution,
        "points": points,
    }

    with open(OUTPUT_MAP_JSON, "w") as f:
        json.dump(map_data, f, indent=2)
    print(f"Saved metadata: {OUTPUT_MAP_JSON}")

    # Create verification image (downscaled with red dots)
    check_scale = 600 / img_width
    check_size = (int(img_width * check_scale), int(img_height * check_scale))
    check_img = stitched.resize(check_size, Image.Resampling.LANCZOS)

    # Draw red dots at each point
    from PIL import ImageDraw
    draw = ImageDraw.Draw(check_img)
    dot_radius = 3  # 6px diameter dot on the 600px-wide check image

    for pt in points:
        check_x = int(pt["x"] * check_scale)
        check_y = int(pt["y"] * check_scale)
        # Draw filled circle
        draw.ellipse(
            [(check_x - dot_radius, check_y - dot_radius),
             (check_x + dot_radius, check_y + dot_radius)],
            fill="red"
        )

    check_img.save(OUTPUT_CHECK)
    print(f"Saved verification: {OUTPUT_CHECK}")

    # Print summary
    print("\n" + "="*60)
    print(f"Map dimensions: {img_width}x{img_height}")
    print(f"Tile source: {TILE_SOURCES[0][0]}")
    print(f"Tiles downloaded: {tiles_downloaded}")
    print(f"Tile pixel size: {tile_px}")
    print("Points:")
    for pt in points:
        print(f"  {pt['chapter']:2d}. {pt['place']:30s} ({pt['x']:4d}, {pt['y']:4d})")


if __name__ == "__main__":
    main()
