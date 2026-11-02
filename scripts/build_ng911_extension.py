#!/usr/bin/env python3
"""
scripts/build_ng911_extension.py

The data half of the NG911 GERS Extension prototypes, one dataset per package, built from the
Overture-only county builds. Each row is keyed on a GERS ID with NENA STA-006 properties in the `ng911`
namespace, and carries no geometry: consumers join on `id`.

  ng911_address         -> addresses/address        (package extensions/ng911-address)
  ng911_road_centerline -> transportation/segment   (package extensions/ng911-road-centerline)

Each writes data/output/extensions/<name>/:
  <name>_ca.parquet    the dataset
  <name>_sample.jsonl  a sample that parses against the package (also copied into the package)
  manifest.json        what a catalog listing reports: rows, field fill, and GERS ID coverage
                       (share of IDs that resolve in the stated Overture release)
Usage: python scripts/build_ng911_extension.py   (after overture_only_counties.py)
"""
import datetime
import glob
import json
import os
import shutil
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from statewide_overture_scorecard import PROJECT_DIR, RELEASE, STATE_BBOX  # noqa: E402

BUILDS = os.path.join(PROJECT_DIR, "data", "output", "overture_only", "*")
OUT_ROOT = os.path.join(PROJECT_DIR, "data", "output", "extensions")
SAMPLE_PER_COUNTY = 5
COUNTY_KEY = "regexp_extract(filename, '/overture_only/([^/]+)/', 1)"
COUNTY_NAME = "array_to_string(list_transform(string_split(county_key, '_'), lambda w: upper(w[1]) || w[2:]), ' ') || ' County'"
ADD_NUMBER = "try_cast(nullif(regexp_extract(house_number, '^[0-9]+'), '') AS INTEGER)"


def address_dataset(c):
    has_unit = "unit" in [r[0] for r in c.execute("DESCRIBE addr").fetchall()]  # carried once the parse keeps units
    c.sql(f"""CREATE TABLE ext AS SELECT overture_id AS id, county_key, struct_pack(
            nguid := 'urn:emergency:uid:gis:SSAP:' || overture_id || ':' || county_key || '.ca.gov',
            add_number := {ADD_NUMBER},
            addnum_suf := nullif(trim(regexp_replace(house_number, '^[0-9]+', '')), ''),
            st_predir := pre_directional,
            st_name := street_name,
            st_posttyp := street_type,
            st_posdir := post_directional,
            unit := {"nullif(trim(unit), '')" if has_unit else "NULL::VARCHAR"},
            post_comm := community_name,
            post_code := postcode,
            county := {COUNTY_NAME},
            state := 'CA',
            country := 'US',
            road_match := RoadMatch,
            road_distance_m := DistanceM::DOUBLE,
            road_segment_id := RoadSegmentId,
            source_url := source_url) AS ng911
        FROM addr""")


def road_centerline_dataset(c):
    # Address ranges: each address matched to a segment (same name, within 50 m) lands on the left or right
    # of it (sign of the cross product with the segment's direction where the address projects onto it).
    # From/To follow the segment's digitized direction: numbers rising along it give From = min, To = max.
    c.sql(f"""CREATE TABLE side AS
        WITH p AS (
            SELECT a.RoadSegmentId AS seg_id, {ADD_NUMBER} AS n, a.postcode, a.community_name, a.geom AS pt,
                   s.geom AS line, ST_LineLocatePoint(s.geom, a.geom) AS f
            FROM addr a JOIN seg s ON s.overture_segment_id = a.RoadSegmentId AND s.county_key = a.county_key
            WHERE a.RoadMatch = 'OK' AND ST_GeometryType(s.geom) = 'LINESTRING'),
        d AS (
            SELECT *, ST_LineInterpolatePoint(line, greatest(f - 0.001, 0)) AS a0,
                      ST_LineInterpolatePoint(line, least(f + 0.001, 1)) AS a1
            FROM p WHERE n IS NOT NULL)
        SELECT seg_id, n, f, postcode, community_name,
               CASE WHEN (ST_X(a1) - ST_X(a0)) * (ST_Y(pt) - ST_Y(a0)) - (ST_Y(a1) - ST_Y(a0)) * (ST_X(pt) - ST_X(a0)) > 0
                    THEN 'L' ELSE 'R' END AS side
        FROM d""")
    c.sql("""CREATE TABLE rng AS
        SELECT seg_id, side, count(*) AS k,
               CASE WHEN coalesce(corr(n, f), 0) >= 0 THEN min(n) ELSE max(n) END AS from_n,
               CASE WHEN coalesce(corr(n, f), 0) >= 0 THEN max(n) ELSE min(n) END AS to_n,
               CASE WHEN bool_and(n % 2 = 0) THEN 'E' WHEN bool_and(n % 2 = 1) THEN 'O' ELSE 'B' END AS parity,
               mode(postcode) AS postcode, mode(community_name) AS postcomm
        FROM side GROUP BY ALL""")
    # ponytail: a segment crossing a county line is kept once, in the county where more of its addresses are,
    # and both sides take that county; per-side counties from the county polygons if border roads matter
    c.sql(f"""CREATE TABLE ext AS
        SELECT s.overture_segment_id AS id, s.county_key, struct_pack(
            nguid := 'urn:emergency:uid:gis:RCL:' || s.overture_segment_id || ':' || s.county_key || '.ca.gov',
            st_predir := s.st_predir,
            st_name := s.st_name,
            st_posttyp := s.st_posttyp,
            road_class := CASE WHEN s.road_class = 'motorway' THEN 'Primary'
                               WHEN s.road_class IN ('trunk', 'primary', 'secondary') THEN 'Secondary'
                               WHEN s.road_class IN ('tertiary', 'residential', 'unclassified', 'living_street') THEN 'Local'
                               WHEN s.road_class = 'service' THEN 'Service Drive'
                               WHEN s.road_class = 'track' THEN 'Vehicular Trail'
                               ELSE 'Other' END,
            fromaddr_l := l.from_n, toaddr_l := l.to_n, fromaddr_r := r.from_n, toaddr_r := r.to_n,
            parity_l := coalesce(l.parity, 'Z'), parity_r := coalesce(r.parity, 'Z'),
            addr_count_l := coalesce(l.k, 0)::INTEGER, addr_count_r := coalesce(r.k, 0)::INTEGER,
            postcode_l := l.postcode, postcode_r := r.postcode,
            postcomm_l := l.postcomm, postcomm_r := r.postcomm,
            county_l := {COUNTY_NAME}, county_r := {COUNTY_NAME},
            state_l := 'CA', state_r := 'CA', country_l := 'US', country_r := 'US',
            source_url := s.osm_edit_url) AS ng911
        FROM seg s
        LEFT JOIN rng l ON l.seg_id = s.overture_segment_id AND l.side = 'L'
        LEFT JOIN rng r ON r.seg_id = s.overture_segment_id AND r.side = 'R'
        WHERE s.st_name IS NOT NULL
        QUALIFY row_number() OVER (PARTITION BY s.overture_segment_id
                                   ORDER BY coalesce(l.k, 0) + coalesce(r.k, 0) DESC, s.county_key) = 1""")


DATASETS = [
    # name, builder, package dir, release path for GERS coverage, target, reference schema package, license note
    ("ng911_address", address_dataset, "ng911-address", "theme=addresses/type=address", "addresses/address",
     "overture-schema-theme-addresses",
     "Address values keep their source licenses (see ng911.source_url); road_* fields derive from Overture "
     "transportation, which is ODbL."),
    ("ng911_road_centerline", road_centerline_dataset, "ng911-road-centerline", "theme=transportation/type=segment",
     "transportation/segment", "overture-schema-theme-transportation",
     "Road names and classes derive from Overture transportation (ODbL); address ranges derive from Overture "
     "addresses, which keep their source licenses."),
]


def write(c, name, package, release_path, target, schema_pkg, license_note):
    out = os.path.join(OUT_ROOT, name)
    os.makedirs(out, exist_ok=True)
    c.sql(f"COPY (SELECT id, ng911 FROM ext ORDER BY county_key, id) TO '{out}/{name}_ca.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")

    # sample: a few rows from every county, in the JSON the package parses
    sample = c.execute(f"""SELECT to_json(struct_pack(id := id, ng911 := ng911))::VARCHAR FROM (
        SELECT *, row_number() OVER (PARTITION BY county_key ORDER BY hash(id)) AS rn FROM ext)
        WHERE rn <= {SAMPLE_PER_COUNTY} ORDER BY county_key, id""").fetchall()
    sample_path = os.path.join(out, f"{name}_sample.jsonl")
    with open(sample_path, "w") as f:
        f.writelines(row[0] + "\n" for row in sample)
    pkg = os.path.join(PROJECT_DIR, "extensions", package)
    os.makedirs(os.path.join(pkg, "sample"), exist_ok=True)
    shutil.copy(sample_path, os.path.join(pkg, "sample"))

    # GERS ID coverage against the stated release (reported, not gated on)
    xmin, ymin, xmax, ymax = STATE_BBOX["CA"]
    total, resolved = c.execute(f"""
        WITH rel AS (SELECT id FROM read_parquet('{RELEASE}/{release_path}/*.parquet', hive_partitioning=1)
                     WHERE bbox.xmin BETWEEN {xmin} AND {xmax} AND bbox.ymin BETWEEN {ymin} AND {ymax})
        SELECT count(*), count(rel.id) FROM ext LEFT JOIN rel USING (id)""").fetchall()[0]
    fields = c.execute("SELECT json_keys(to_json(ng911)) FROM ext LIMIT 1").fetchall()[0][0]  # struct order
    fill = c.execute("SELECT " + ", ".join(f"round(100.0 * count(ng911.{f}) / count(*), 1)" for f in fields) + " FROM ext").fetchall()[0]
    manifest = {
        "extension": f"overture-extension-{package}",
        "package_version": "0.1.0",
        "status": "prototype",
        "target_feature_type": target,
        "join_key": "id (GERS ID)",
        "publisher_id_column": "ng911.nguid",
        "reference_schema": f"{schema_pkg} >=2.0,<3",
        "gers_id_coverage": {"release": RELEASE.rsplit("/", 1)[-1], "ids": total, "resolved": resolved,
                             "pct": round(100.0 * resolved / total, 2) if total else None},
        "rows": total,
        "counties": c.execute("SELECT count(DISTINCT county_key) FROM ext").fetchall()[0][0],
        "field_fill_pct": dict(zip(fields, fill)),
        "files": {"data": f"{name}_ca.parquet", "sample": f"{name}_sample.jsonl"},
        "license_note": license_note,  # ponytail: the license is the publisher's call
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"\n[{name}]", json.dumps({k: manifest[k] for k in ("rows", "counties", "gers_id_coverage")}))
    print("fill %:", manifest["field_fill_pct"])


def main():
    addr_files = glob.glob(os.path.join(BUILDS, "address_points.parquet"))
    if not addr_files:
        sys.exit(f"No Overture-only builds under {BUILDS}; run overture_only_counties.py first")
    c = duckdb.connect()
    c.sql("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2'; SET geometry_always_xy = true;")
    c.sql(f"CREATE TABLE addr AS SELECT *, {COUNTY_KEY} AS county_key FROM read_parquet({addr_files!r}, filename = true, union_by_name = true)")
    c.sql(f"""CREATE TABLE seg AS SELECT *, {COUNTY_KEY} AS county_key
              FROM read_parquet({glob.glob(os.path.join(BUILDS, 'road_centerlines.parquet'))!r}, filename = true, union_by_name = true)""")
    for name, build, *meta in DATASETS:
        build(c)
        write(c, name, *meta)
        c.sql("DROP TABLE ext")


if __name__ == "__main__":
    main()
