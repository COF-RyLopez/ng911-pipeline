#!/usr/bin/env python3
"""
scripts/build_ng911_extension.py

The data half of the NG911 GERS Extension prototype (package: extensions/ng911-address): one row per
Overture address in the Overture-only county builds, keyed on its GERS ID, with the NENA STA-006
properties in the `ng911` namespace. No geometry: consumers join it to Overture addresses on `id`.

Writes data/output/extensions/ng911_address/:
  ng911_address_ca.parquet   the dataset
  ng911_address_sample.jsonl a sample that parses against the package (also copied into the package)
  manifest.json              what a catalog listing reports: rows, field fill, and GERS ID coverage
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

SRC = os.path.join(PROJECT_DIR, "data", "output", "overture_only", "*", "address_points.parquet")
OUT = os.path.join(PROJECT_DIR, "data", "output", "extensions", "ng911_address")
PACKAGE = os.path.join(PROJECT_DIR, "extensions", "ng911-address")
SAMPLE_PER_COUNTY = 5


def main():
    files = glob.glob(SRC)
    if not files:
        sys.exit(f"No Overture-only builds at {SRC}; run overture_only_counties.py first")
    os.makedirs(OUT, exist_ok=True)
    c = duckdb.connect()
    c.sql("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    c.sql(f"CREATE VIEW src AS SELECT * FROM read_parquet({files!r}, filename = true, union_by_name = true)")
    has_unit = "unit" in [r[0] for r in c.execute("DESCRIBE src").fetchall()]  # carried once the parse keeps units
    c.sql(f"""CREATE TABLE ext AS
        WITH s AS (
            SELECT *, regexp_extract(filename, '/overture_only/([^/]+)/', 1) AS county_key FROM src)
        SELECT overture_id AS id, county_key, struct_pack(
            nguid := 'urn:emergency:uid:gis:SSAP:' || overture_id || ':' || county_key || '.ca.gov',
            add_number := try_cast(nullif(regexp_extract(house_number, '^[0-9]+'), '') AS INTEGER),
            addnum_suf := nullif(trim(regexp_replace(house_number, '^[0-9]+', '')), ''),
            st_predir := pre_directional,
            st_name := street_name,
            st_posttyp := street_type,
            unit := {"nullif(trim(unit), '')" if has_unit else "NULL::VARCHAR"},
            post_comm := community_name,
            post_code := postcode,
            county := array_to_string(list_transform(string_split(county_key, '_'), lambda w: upper(w[1]) || w[2:]), ' ') || ' County',
            state := 'CA',
            country := 'US',
            road_match := RoadMatch,
            road_distance_m := DistanceM::DOUBLE,
            road_segment_id := RoadSegmentId,
            source_url := source_url) AS ng911
        FROM s""")
    c.sql(f"COPY (SELECT id, ng911 FROM ext ORDER BY county_key, id) TO '{OUT}/ng911_address_ca.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")

    # sample: a few rows from every county, in the JSON the package parses
    sample = c.execute(f"""SELECT to_json(struct_pack(id := id, ng911 := ng911))::VARCHAR FROM (
        SELECT *, row_number() OVER (PARTITION BY county_key ORDER BY hash(id)) AS rn FROM ext)
        WHERE rn <= {SAMPLE_PER_COUNTY} ORDER BY county_key, id""").fetchall()
    sample_path = os.path.join(OUT, "ng911_address_sample.jsonl")
    with open(sample_path, "w") as f:
        f.writelines(row[0] + "\n" for row in sample)
    os.makedirs(os.path.join(PACKAGE, "sample"), exist_ok=True)
    shutil.copy(sample_path, os.path.join(PACKAGE, "sample"))

    # GERS ID coverage against the stated release (reported, not gated on)
    xmin, ymin, xmax, ymax = STATE_BBOX["CA"]
    total, resolved = c.execute(f"""
        WITH rel AS (SELECT id FROM read_parquet('{RELEASE}/theme=addresses/type=address/*.parquet', hive_partitioning=1)
                     WHERE country = 'US' AND bbox.xmin BETWEEN {xmin} AND {xmax} AND bbox.ymin BETWEEN {ymin} AND {ymax})
        SELECT count(*), count(rel.id) FROM ext LEFT JOIN rel USING (id)""").fetchall()[0]
    fields = c.execute("SELECT json_keys(to_json(ng911)) FROM ext LIMIT 1").fetchall()[0][0]  # struct order
    fill = c.execute("SELECT " + ", ".join(f"round(100.0 * count(ng911.{f}) / count(*), 1)" for f in fields) + " FROM ext").fetchall()[0]
    manifest = {
        "extension": "overture-extension-ng911-address",
        "package_version": "0.1.0",
        "status": "prototype",
        "target_feature_type": "addresses/address",
        "join_key": "id (GERS ID)",
        "publisher_id_column": "ng911.nguid",
        "reference_schema": "overture-schema-theme-addresses >=2.0,<3",
        "gers_id_coverage": {"release": RELEASE.rsplit("/", 1)[-1], "ids": total, "resolved": resolved,
                             "pct": round(100.0 * resolved / total, 2) if total else None},
        "rows": total,
        "counties": c.execute("SELECT count(DISTINCT county_key) FROM ext").fetchall()[0][0],
        "field_fill_pct": dict(zip(fields, fill)),
        "files": {"data": "ng911_address_ca.parquet", "sample": "ng911_address_sample.jsonl"},
        # ponytail: the license is the publisher's call; road_match derives from Overture transportation (ODbL)
        "license_note": "Address values keep their source licenses (see ng911.source_url); road_* fields derive "
                        "from Overture transportation, which is ODbL.",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print(json.dumps({k: manifest[k] for k in ("rows", "counties", "gers_id_coverage")}, indent=1))
    print("fill %:", manifest["field_fill_pct"])


if __name__ == "__main__":
    main()
