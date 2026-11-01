#!/usr/bin/env python3
"""
scripts/overture_only_counties.py

Product 1 for counties with no county GIS in this pipeline: build the Overture-only NG911 layers
(address points, road centerlines, address-to-road fishbones, localities) for the counties the
statewide scorecard rates weakest, using the same oo_* dbt models as the Fresno build.

Each county gets a one-off registry entry passed through --vars, so dbt_project.yml and the
Fresno/Kings caches are untouched (the Overture caches are swapped in and restored afterwards).

Writes data/output/overture_only/<county>/{address_points,road_centerlines}.parquet, address_points.geojson
(for the map) and
data/output/overture_only/counties_summary.{csv,json}.
Usage: python scripts/overture_only_counties.py [--top 5]   (after statewide_overture_scorecard.py)
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import county_config  # noqa: E402
import fetch_pilot_data as fpd  # noqa: E402

PROJECT_DIR = county_config.PROJECT_DIR
OUT_DIR = os.path.join(PROJECT_DIR, "data", "output", "overture_only")
STATEWIDE = os.path.join(PROJECT_DIR, "data", "output", "statewide", "ca_overture_county_scorecard.geojson")
SWAPPED = ["overture_addresses.parquet", "overture_transportation.parquet", "overture_divisions.parquet"]  # county-extent caches
MODELS = "+oo_fishbones oo_localities"  # oo_fishbones pulls in the boundary, points and centerlines


def bbox(geom):
    pts = [p for poly in (geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]])
           for ring in poly for p in ring]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [round(min(xs) - 0.01, 3), round(min(ys) - 0.01, 3), round(max(xs) + 0.01, 3), round(max(ys) + 0.01, 3)]


def weakest(top):
    """The `top` counties with the lowest min(address completeness, named public roads), not already built."""
    built = {c["name"] for c in county_config.COUNTIES.values()}
    feats = json.load(open(STATEWIDE))["features"]
    score = lambda p: min(p["PctNumberAndStreet"] or 0, p["PctPublicRoadKmNamed"] or 0)
    feats = [f for f in feats if f["properties"]["County"].removesuffix(" County").upper() not in built]
    return sorted(feats, key=lambda f: score(f["properties"]))[:top]


def build(feature, dbt_bin):
    name = feature["properties"]["County"].removesuffix(" County").upper()
    key = name.lower().replace(" ", "_")
    entry = {"name": name, "label": f"{name.title()} County, CA", "agency_domain": f"{key}.ca.gov",
             "agency_name": f"County of {name.title()}", "boundary_layers": False, "bbox": bbox(feature["geometry"])}
    b = entry["bbox"]
    print(f"\n[{name}] bbox {b}")
    fpd.OVERTURE_BBOX.update(minx=b[0], miny=b[1], maxx=b[2], maxy=b[3])
    fpd.fetch_overture_addresses()
    fpd.fetch_overture_transportation()
    fpd.fetch_overture_divisions()  # the county polygon every oo_ model is clipped to

    dbt_vars = {"county": key, "counties": {**county_config.COUNTIES, key: entry}}
    r = subprocess.run([dbt_bin, "run", "--profiles-dir", ".", "--select", *MODELS.split(), "--vars", json.dumps(dbt_vars)],
                       cwd=PROJECT_DIR, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[{name}] dbt failed:\n{r.stdout[-3000:]}\n{r.stderr[-2000:]}")
        return None

    out = os.path.join(OUT_DIR, key)
    os.makedirs(out, exist_ok=True)
    with duckdb.connect(os.path.join(PROJECT_DIR, "ng911_database.duckdb"), read_only=True) as c:
        c.sql("LOAD spatial")
        c.sql(f"COPY oo_address_points TO '{out}/address_points.parquet' (FORMAT PARQUET)")
        c.sql(f"COPY oo_road_centerlines TO '{out}/road_centerlines.parquet' (FORMAT PARQUET)")
        # map layer: each point with its fishbone result (same-named road within 50 m / farther / none)
        pts = c.execute("""
            SELECT round(ST_X(p.geom), 6), round(ST_Y(p.geom), 6),
                   trim(concat_ws(' ', p.house_number, p.pre_directional, p.street_name, p.street_type)),
                   CASE WHEN f.overture_id IS NULL THEN 'NO_NAMED_ROAD'
                        WHEN f.is_excessive_offset THEN 'FAR' ELSE 'OK' END, f.distance_meters
            FROM oo_address_points p LEFT JOIN oo_fishbones f USING (overture_id)""").fetchall()
        with open(f"{out}/address_points.geojson", "w") as fh:
            json.dump({"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [x, y]},
                 "properties": {"Address": a, "RoadMatch": m, "DistanceM": d}} for x, y, a, m, d in pts]},
                fh, separators=(",", ":"), default=float)
        row = c.execute("""
            WITH a AS (SELECT count(*) AS n, count(*) FILTER (WHERE house_number IS NULL) AS no_num FROM oo_address_points),
                 f AS (SELECT count(*) AS n, count(*) FILTER (WHERE NOT is_excessive_offset) AS near FROM oo_fishbones),
                 r AS (SELECT count(*) AS n, sum(ST_Length(geom)) * 111.32 AS km FROM oo_road_centerlines)
            SELECT a.n, round(100.0 * a.no_num / nullif(a.n, 0), 1),
                   round(100.0 * f.n / nullif(a.n, 0), 1), round(100.0 * f.near / nullif(f.n, 0), 1),
                   r.n, round(r.km), (SELECT count(*) FROM oo_localities)
            FROM a, f, r""").fetchall()[0]
    cols = ["AddressPoints", "PctMissingNumber", "PctMatchedToNamedRoad", "PctMatchedWithin50m",
            "RoadSegments", "RoadKm", "Localities"]
    summary = {"County": entry["label"], "Key": key, **dict(zip(cols, row))}
    print(f"[{name}] {summary}")
    return summary if row[0] else None  # no address points: the county polygon or a fetch came back empty


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=5)
    top = ap.parse_args().top
    dbt_bin = os.path.join(PROJECT_DIR, ".venv", "bin", "dbt")
    dbt_bin = dbt_bin if os.path.exists(dbt_bin) else "dbt"
    for f in SWAPPED:  # keep the registered counties' caches; restored below even if a build fails
        p = os.path.join(fpd.CACHE_DIR, f)
        if os.path.exists(p):
            shutil.move(p, p + ".bak")
    try:
        rows = [s for s in (build(f, dbt_bin) for f in weakest(top)) if s]
    finally:
        for f in SWAPPED:
            p = os.path.join(fpd.CACHE_DIR, f)
            if os.path.exists(p + ".bak"):
                shutil.move(p + ".bak", p)

    if rows:
        with open(os.path.join(OUT_DIR, "counties_summary.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        with open(os.path.join(OUT_DIR, "counties_summary.json"), "w") as fh:
            json.dump(rows, fh, indent=1, default=float)
    print(f"\nBuilt {len(rows)} of {top} counties into {OUT_DIR}")
    if len(rows) < top:
        sys.exit(1)


if __name__ == "__main__":
    main()
