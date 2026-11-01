#!/usr/bin/env python3
"""
scripts/statewide_overture_scorecard.py

Product 1 at state scale: how far Overture data alone gets toward NG911 address points and road
centerlines in every county of a state, without any county GIS.

Writes data/output/statewide/<st>_overture_county_scorecard.{csv,geojson} (one row / polygon per county).
Usage: python scripts/statewide_overture_scorecard.py [--state CA]
"""
import argparse
import json
import os
import urllib.request

import duckdb

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PROJECT_DIR, "data", "output", "statewide")
RELEASE = "s3://overturemaps-us-west-2/release/2026-09-23.1"  # keep in step with fetch_pilot_data.py
STATE_FIPS = {"CA": "06"}  # ponytail: add a state here (and its bbox below) to score it
STATE_BBOX = {"CA": (-124.5, 32.5, -114.1, 42.1)}
# Road classes a 911 centerline layer carries; tracks, service roads, driveways and paths are left out
PUBLIC_CLASSES = ("motorway", "trunk", "primary", "secondary", "tertiary", "residential", "unclassified", "living_street")


def census_housing_units(fips):
    """2020 Census housing units by county name ('Fresno County'); {} if the API is unreachable."""
    url = f"https://api.census.gov/data/2020/dec/pl?get=NAME,H1_001N&for=county:*&in=state:{fips}"
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            rows = json.load(resp)[1:]
        return {name.split(",")[0]: int(hu) for name, hu, *_ in rows}
    except Exception as e:
        print(f"  Census housing units unavailable ({e}); coverage ratio left blank")
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="CA")
    st = ap.parse_args().state.upper()
    xmin, ymin, xmax, ymax = STATE_BBOX[st]
    in_box = f"bbox.xmin BETWEEN {xmin} AND {xmax} AND bbox.ymin BETWEEN {ymin} AND {ymax}"
    os.makedirs(OUT_DIR, exist_ok=True)

    c = duckdb.connect()
    c.sql("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    c.sql(f"""CREATE TABLE cty AS SELECT names."primary" AS county, geometry AS geom,
                     ST_SimplifyPreserveTopology(geometry, 0.002) AS g
              FROM read_parquet('{RELEASE}/theme=divisions/type=division_area/*.parquet', hive_partitioning=1)
              WHERE subtype = 'county' AND class = 'land' AND region = 'US-{st}'""")
    print(f"[{st}] {c.execute('SELECT count(*) FROM cty').fetchall()[0][0]} counties")

    c.sql(f"""CREATE TABLE a AS SELECT
                  coalesce(trim(street), '') <> '' AS has_street, coalesce(trim(number), '') <> '' AS has_number,
                  unit IS NOT NULL AS has_unit, sources[1].dataset = 'NAD' AS is_nad, ST_X(geometry) AS x, ST_Y(geometry) AS y
              FROM read_parquet('{RELEASE}/theme=addresses/type=address/*.parquet', hive_partitioning=1)
              WHERE country = 'US' AND address_levels[1].value = '{st}' AND {in_box}""")
    c.sql(f"""CREATE TABLE r AS SELECT names."primary" IS NOT NULL AS named,
                  ST_Length_Spheroid(ST_FlipCoordinates(geometry)) / 1000 AS km, ST_Centroid(geometry) AS pt
              FROM read_parquet('{RELEASE}/theme=transportation/type=segment/*.parquet', hive_partitioning=1)
              WHERE subtype = 'road' AND class IN {PUBLIC_CLASSES} AND {in_box}""")
    print(f"[{st}] {c.execute('SELECT count(*) FROM a').fetchall()[0][0]:,} address points, "
          f"{c.execute('SELECT count(*) FROM r').fetchall()[0][0]:,} public road segments")

    hu = census_housing_units(STATE_FIPS[st])
    c.sql("CREATE TABLE hu (county VARCHAR, housing_units BIGINT)")
    if hu:
        c.executemany("INSERT INTO hu VALUES (?, ?)", list(hu.items()))

    c.sql("""CREATE TABLE s AS
        WITH aa AS (
            SELECT cty.county, count(*) AS n,
                   count(*) FILTER (WHERE has_street AND has_number) AS complete,
                   count(*) FILTER (WHERE NOT has_number) AS no_number,
                   count(*) FILTER (WHERE has_unit) AS units, count(*) FILTER (WHERE is_nad) AS nad
            FROM a JOIN cty ON ST_Contains(cty.g, ST_Point(a.x, a.y)) GROUP BY 1),
        rr AS (
            SELECT cty.county, sum(km) AS km, sum(km) FILTER (WHERE named) AS named_km
            FROM r JOIN cty ON ST_Contains(cty.g, r.pt) GROUP BY 1)
        SELECT cty.county AS County,
               coalesce(aa.n, 0) AS AddressPoints,
               hu.housing_units AS HousingUnits2020,
               round(aa.n / nullif(hu.housing_units, 0), 2) AS AddressesPerHousingUnit,
               round(100.0 * aa.complete / nullif(aa.n, 0), 1) AS PctNumberAndStreet,
               round(100.0 * aa.no_number / nullif(aa.n, 0), 1) AS PctMissingNumber,
               round(100.0 * aa.units / nullif(aa.n, 0), 1) AS PctWithUnit,
               round(100.0 * aa.nad / nullif(aa.n, 0), 1) AS PctFromNAD,
               round(rr.km) AS PublicRoadKm,
               round(100.0 * rr.named_km / nullif(rr.km, 0), 1) AS PctPublicRoadKmNamed,
               cty.geom
        FROM cty LEFT JOIN aa USING (county) LEFT JOIN rr USING (county) LEFT JOIN hu USING (county)
        ORDER BY County""")

    csv_path = os.path.join(OUT_DIR, f"{st.lower()}_overture_county_scorecard.csv")
    c.sql(f"COPY (SELECT * EXCLUDE (geom) FROM s) TO '{csv_path}' (HEADER)")
    rows = c.execute("SELECT * EXCLUDE (geom), ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.005)) FROM s")
    cols = [d[0] for d in rows.description]
    feats = [{"type": "Feature", "properties": dict(zip(cols[:-1], row[:-1])), "geometry": json.loads(row[-1])}
             for row in rows.fetchall()]
    with open(os.path.join(OUT_DIR, f"{st.lower()}_overture_county_scorecard.geojson"), "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, separators=(",", ":"), default=float)

    print(c.sql("""SELECT sum(AddressPoints) AS address_points, sum(HousingUnits2020) AS housing_units,
                          round(100.0 * sum(AddressPoints * PctNumberAndStreet / 100) / sum(AddressPoints), 1) AS pct_number_and_street,
                          round(sum(PublicRoadKm)) AS public_road_km,
                          round(100.0 * sum(PublicRoadKm * PctPublicRoadKmNamed / 100) / sum(PublicRoadKm), 1) AS pct_public_road_named
                   FROM s"""))
    c.sql("""SELECT County, AddressPoints, AddressesPerHousingUnit, PctNumberAndStreet, PctPublicRoadKmNamed FROM s
                   ORDER BY least(coalesce(AddressesPerHousingUnit, 9), PctNumberAndStreet / 100, PctPublicRoadKmNamed / 100)
                   LIMIT 10""").show(max_width=200)
    print(f"Wrote {csv_path} and .geojson")


if __name__ == "__main__":
    main()
