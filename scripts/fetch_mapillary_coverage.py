#!/usr/bin/env python3
"""
fetch_mapillary_coverage.py
Caches Mapillary street-level imagery coverage (sequence lines with capture dates)
for every zoom-12 tile that contains a Fresno address point.

Source: Mapillary coverage vector tiles, layer "sequence"
  https://tiles.mapillary.com/maps/vtp/mly1_public/2/{z}/{x}/{y}
Output: data/cache/mapillary_sequences.parquet (geom EPSG:4326, captured_at, is_pano)

Token: MAPILLARY_TOKEN env var, else the public client token the viewer already ships.
"""

import math
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import duckdb

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
TILE_DIR = os.path.join(CACHE_DIR, "mapillary_tiles")
OUTPUT_PARQUET = os.path.join(CACHE_DIR, "mapillary_sequences.parquet")
POINTS_PARQUET = os.path.join(CACHE_DIR, "county_addresses.parquet")
TILE_URL = "https://tiles.mapillary.com/maps/vtp/mly1_public/2/{z}/{x}/{y}?access_token={t}"
DEFAULT_TOKEN = "MLY|26275324248758064|7819d63bee8179a083cdd76e20557967"
Z = 12  # ponytail: z12 sequence lines are generalized but well within the 50 m check; z14 tiles are ~10x heavier


def tile_of(lon, lat, z=Z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def fetch_mapillary_coverage(points_parquet=POINTS_PARQUET):
    """Returns the number of sequence features cached."""
    token = os.environ.get("MAPILLARY_TOKEN") or DEFAULT_TOKEN
    os.makedirs(TILE_DIR, exist_ok=True)
    con = duckdb.connect()
    con.execute("LOAD spatial")

    pts = con.execute(f"SELECT DISTINCT longitude, latitude FROM read_parquet('{points_parquet}') "
                      "WHERE longitude IS NOT NULL AND latitude IS NOT NULL").fetchall()
    tiles = sorted({tile_of(lon, lat) for lon, lat in pts})
    print(f"\n[Mapillary] Fetching street imagery coverage: {len(tiles)} z{Z} tiles for {len(pts):,} address locations")

    def fetch(xy):
        x, y = xy
        path = os.path.join(TILE_DIR, f"{Z}_{x}_{y}.pbf")
        url = TILE_URL.format(z=Z, x=x, y=y, t=token)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Fresno-NG911/1.0"}), timeout=60) as r:
                    data = r.read()
                with open(path, "wb") as f:
                    f.write(data)
                return path, x, y
            except Exception as e:
                if attempt == 2:
                    raise RuntimeError(f"Mapillary tile {Z}/{x}/{y} failed: {e}")
                time.sleep(2 ** attempt)

    with ThreadPoolExecutor(max_workers=8) as pool:
        files = list(pool.map(fetch, tiles))

    con.execute("CREATE TABLE seq (captured_at TIMESTAMP, is_pano BOOLEAN, geom GEOMETRY)")
    for path, x, y in files:
        if os.path.getsize(path) == 0:
            continue  # tile with no imagery
        layers = [l["name"] for l in con.execute(f"SELECT layers FROM st_read_meta('{path}')").fetchone()[0]]
        if "sequence" not in layers:
            continue
        con.execute(f"""
            INSERT INTO seq
            SELECT to_timestamp(captured_at / 1000)::TIMESTAMP, is_pano,
                   ST_Transform(geom, 'EPSG:3857', 'EPSG:4326', always_xy := true)
            FROM st_read('{path}', layer = 'sequence', open_options = ['X={x}', 'Y={y}', 'Z={Z}'])
        """)

    count = con.execute("SELECT count(*) FROM seq").fetchone()[0]
    con.execute(f"COPY seq TO '{OUTPUT_PARQUET}' (FORMAT PARQUET)")
    print(f"  -> Saved {count:,} Mapillary sequence segments to {OUTPUT_PARQUET}")
    return count


def write_empty_stub():
    con = duckdb.connect()
    con.execute("LOAD spatial")
    con.execute(f"COPY (SELECT NULL::TIMESTAMP AS captured_at, NULL::BOOLEAN AS is_pano, "
                f"NULL::GEOMETRY AS geom WHERE 1=0) TO '{OUTPUT_PARQUET}' (FORMAT PARQUET)")


if __name__ == "__main__":
    import sys
    fetch_mapillary_coverage(sys.argv[1] if len(sys.argv) > 1 else POINTS_PARQUET)
