#!/usr/bin/env python3
"""
scripts/build_ng911_hydrology.py

NENA-STA-006.3 Hydrology Line and Hydrology Polygon layers for California from the USGS 3D Hydrography Program
(3DHP, public domain). This is a supplemental dataset, not a GERS Extension: Overture's base/water IDs aren't
stable GERS IDs, so the layers carry their own geometry and 3DHP's persistent `id3dhp`.

Writes data/output/supplemental/ng911_hydrology/{ng911_hydrology_line_ca,ng911_hydrology_polygon_ca}.parquet
(GeoParquet) and manifest.json. Usage: python scripts/build_ng911_hydrology.py   (~40 min; run by .github/workflows/hydrology.yml monthly)
"""
import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_ng911_extension import PROJECT_DIR, TIGER_COUNTIES, load_places  # noqa: E402

SERVICE = "https://hydro.nationalmap.gov/arcgis/rest/services/3DHP_all/FeatureServer"
# ponytail: named flowlines only (372K in CA); all flowlines run to millions, mostly unnamed channels a 911
# caller can't name. Add them if a county wants the full network.
LAYERS = {"line": (50, "gnisid IS NOT NULL"), "polygon": (60, "1=1")}
FIELDS = "id3dhp,gnisid,gnisidlabel,featuretypelabel,mainstemid"
TILES = [(x, y) for x in range(-125, -114) for y in range(32, 42)]  # 1° tiles over California


def fetch_tile(layer, where, x, y, size=1.0):
    """Every feature in one tile, paged at the service's 2,500 limit. A tile the service keeps timing out on is
    split into quarters (down to 1/8°), since dense tiles are what time out."""
    rows, offset = [], 0
    while True:
        url = (f"{SERVICE}/{layer}/query?where={urllib.parse.quote(where)}&geometry={x},{y},{x + size},{y + size}"
               "&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects"
               f"&outFields={FIELDS}&outSR=4326&maxAllowableOffset=0.0001&geometryPrecision=6"
               f"&resultRecordCount=2500&resultOffset={offset}&f=geojson")
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ng911-pipeline"}), timeout=120) as r:
                    page = json.load(r)
                break
            except Exception:
                time.sleep(5 * 3 ** attempt)
        else:
            if size <= 0.125:
                raise RuntimeError(f"3DHP layer {layer} keeps failing at {x},{y} ({size}°)")
            h = size / 2  # restart this tile as four smaller ones (duplicates are dropped later)
            return [r for dx in (0, h) for dy in (0, h) for r in fetch_tile(layer, where, x + dx, y + dy, h)]
        rows += [(f["properties"]["id3dhp"], f["properties"]["gnisid"], f["properties"]["gnisidlabel"],
                  f["properties"]["featuretypelabel"], f["properties"]["mainstemid"], json.dumps(f["geometry"]))
                 for f in page["features"] if f["geometry"]]
        offset += len(page["features"])
        if not (page.get("exceededTransferLimit") or page.get("properties", {}).get("exceededTransferLimit")):
            return rows


def main():
    updated = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    out = os.path.join(PROJECT_DIR, "data", "output", "supplemental", "ng911_hydrology")  # its own R2 part
    os.makedirs(out, exist_ok=True)
    c = duckdb.connect()
    c.sql("INSTALL spatial; LOAD spatial; SET geometry_always_xy = true;")
    load_places(c, "county", TIGER_COUNTIES, "BASENAME")
    layers = {}
    for kind, (layer, where) in LAYERS.items():
        with ThreadPoolExecutor(4) as pool:
            rows = [r for tile in pool.map(lambda t: fetch_tile(layer, where, *t), TILES) for r in tile]
        c.execute("CREATE OR REPLACE TABLE raw (id3dhp VARCHAR, gnisid BIGINT, name VARCHAR, ftype VARCHAR, mainstem VARCHAR, gj VARCHAR)")
        c.executemany("INSERT INTO raw VALUES (?, ?, ?, ?, ?, ?)", rows)
        p = "hs" if kind == "line" else "hp"
        # one row per id3dhp (features crossing tiles come back twice); county from a point on the feature;
        # California only (the tiles also cover NV, AZ, OR and MX)
        c.sql(f"""CREATE OR REPLACE TABLE h AS
            WITH g AS (SELECT id3dhp, any_value(gnisid) AS gnisid, any_value(name) AS name, any_value(ftype) AS ftype,
                              any_value(mainstem) AS mainstem, ST_GeomFromGeoJSON(any_value(gj)) AS geom
                       FROM raw GROUP BY 1)
            SELECT g.*, lower(replace(c.name, ' ', '_')) AS county_key
            FROM g JOIN county c ON ST_Intersects(c.geom, ST_PointOnSurface(g.geom))
            QUALIFY row_number() OVER (PARTITION BY g.id3dhp ORDER BY c.name) = 1""")
        path = f"{out}/ng911_hydrology_{kind}_ca.parquet"
        c.sql(f"""COPY (SELECT county_key || '.ca.gov' AS discrpagid, '{updated}' AS dateupdate,
                         'urn:emergency:uid:gis:{p.upper()}:' || id3dhp || ':' || county_key || '.ca.gov' AS nguid,
                         ftype AS {p}_type, name AS {p}_name,
                         id3dhp, gnisid, mainstem AS mainstem_uri, geom AS geometry
                  FROM h ORDER BY county_key, id3dhp) TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
        n, named, counties = c.execute("SELECT count(*), count(name), count(DISTINCT county_key) FROM h").fetchall()[0]
        types = dict(c.execute("SELECT ftype, count(*) FROM h GROUP BY 1 ORDER BY 2 DESC").fetchall())
        layers[kind] = {"nena_layer": "HydrologyLine" if kind == "line" else "HydrologyPolygon",
                        "file": os.path.basename(path), "rows": n, "named_pct": round(100.0 * named / n, 1) if n else None,
                        "counties": counties, f"{p}_type_counts": types}
        print(f"[ng911_hydrology {kind}] {n:,} features, {counties} counties, types {types}")
    tiles(c, out)
    manifest = {
        "dataset": "ng911-hydrology", "status": "prototype", "kind": "supplemental dataset (not a GERS Extension)",
        "why_not_an_extension": "Overture base/water IDs aren't stable GERS IDs; 3DHP's id3dhp is persistent",
        "source": f"USGS 3D Hydrography Program, {SERVICE} (public domain); NHD fills areas 3DHP hasn't remapped",
        "nena": {"standard": "NENA-STA-006.3-2026", "mandatory_fields": ["discrpagid", "dateupdate", "nguid"],
                 "records_with_all_mandatory_fields_pct": 100.0,
                 "scope": "named flowlines (gnisid) as HydrologyLine; all waterbodies as HydrologyPolygon"},
        "layers": layers, "generated_at": updated,
    }
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)


def tiles(c, out):
    """App 1 map layers: hydrology lines and polygons as PMTiles next to the data (same R2 part)."""
    import build_pmtiles as bp
    engine = bp.pick_engine()
    if engine is None:
        print("[WARNING] Neither tylertoo nor tippecanoe is installed; skipping the hydrology map tiles.")
        return
    attribution = "USGS 3D Hydrography Program (3DHP)"
    bp.build_layer(c, engine, "hydrology_lines", f"{out}/ng911_hydrology_line_ca.parquet",
                   "hs_name AS Name, hs_type AS Type, id3dhp", "geometry",
                   ["-Z9", "-z14", "--drop-densest-as-needed"], f"{out}/tiles/hydrology_lines.pmtiles", attribution=attribution)
    bp.build_layer(c, engine, "hydrology_polygons", f"{out}/ng911_hydrology_polygon_ca.parquet",
                   "hp_name AS Name, hp_type AS Type, id3dhp", "geometry",
                   ["-Z7", "-z14", "--coalesce-densest-as-needed"], f"{out}/tiles/hydrology_polygons.pmtiles", attribution=attribution)


if __name__ == "__main__":
    main()
