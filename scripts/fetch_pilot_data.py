#!/usr/bin/env python3
"""
scripts/fetch_pilot_data.py

Ingests and caches authoritative geospatial data for Fresno County NG911:
1. Ingests Fresno County Site/Structure Address Points (REGIONAL_ADDRESS_VW/FeatureServer/1).
2. Ingests Fresno County Authoritative Street Centerlines (REGIONAL_STREETS_VW/FeatureServer/1).
3. Ingests Fresno County Emergency Service Boundaries (CAD/PSAP, Fire, City Limits).
4. Ingests Overture Maps Address Points (S3 GeoParquet scoped to county extent).
5. Ingests Overture Maps Transportation Segments (S3 GeoParquet scoped to county extent).
6. Ingests Overture Maps Landmark Places (S3 GeoParquet scoped to county extent).
Caches all datasets locally in data/cache/ for deterministic dbt runs.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import duckdb
import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Full Fresno County Extent (EPSG:4326)
FRESNO_COUNTY_BBOX = {
    "minx": -120.92,
    "maxx": -118.36,
    "miny": 35.91,
    "maxy": 37.58
}

def fetch_fresno_county_addresses():
    output_parquet = os.path.join(CACHE_DIR, "county_addresses.parquet")
    print(f"\n[1/6] Fetching all Fresno County addresses from ArcGIS FeatureServer...")
    
    base_url = "https://services3.arcgis.com/ibgDyuD2DLBge82s/arcgis/rest/services/REGIONAL_ADDRESS_VW/FeatureServer/1/query"
    req = urllib.request.Request(
        f"{base_url}?where=ADDRESS_STATUS%3D%27ACTIVE%27+AND+ADDRESS_NUMBER+IS+NOT+NULL&returnCountOnly=true&f=json",
        headers={"User-Agent": "Fresno-NG911/1.0"}
    )
    with urllib.request.urlopen(req) as resp:
        total_count = json.loads(resp.read().decode("utf-8"))["count"]
    print(f"  Target record count: {total_count:,} addresses")

    offsets = list(range(0, total_count, 2000))

    def fetch_page(offset):
        params = {
            "where": "ADDRESS_STATUS='ACTIVE' AND ADDRESS_NUMBER IS NOT NULL",
            "outFields": "OBJECTID,ADDRESS_NUMBER,ADDRESS_FRACTION,STREET_DIRECTION,STREET_NAME,STREET_TYPE,STREET_POST_DIRECTION,ADDRESS_UNIT,ADDRESS_ZIP5,ADDRESS_ZIPCITY,AGENCY_NAME",
            "outSR": "4326",
            "resultOffset": offset,
            "resultRecordCount": 2000,
            "f": "json"
        }
        full_url = f"{base_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(full_url, headers={"User-Agent": "Fresno-NG911/1.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            records = []
            for f in data.get("features", []):
                attr = f.get("attributes", {})
                geom = f.get("geometry", {})
                records.append({
                    "county_id": str(attr.get("OBJECTID")),
                    "house_number": str(attr.get("ADDRESS_NUMBER") or ""),
                    "house_number_suffix": attr.get("ADDRESS_FRACTION"),
                    "pre_directional": attr.get("STREET_DIRECTION"),
                    "street_name": attr.get("STREET_NAME"),
                    "street_type": attr.get("STREET_TYPE"),
                    "post_directional": attr.get("STREET_POST_DIRECTION"),
                    "unit": attr.get("ADDRESS_UNIT"),
                    "community_name": attr.get("ADDRESS_ZIPCITY") or "FRESNO",
                    "postcode": str(attr.get("ADDRESS_ZIP5") or ""),
                    "longitude": float(geom.get("x")) if geom.get("x") is not None else None,
                    "latitude": float(geom.get("y")) if geom.get("y") is not None else None,
                    "source_agency": attr.get("AGENCY_NAME") or "County of Fresno"
                })
            return records

    t0 = time.time()
    all_records = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for batch in ex.map(fetch_page, offsets):
            all_records.extend(batch)
    print(f"  Retrieved {len(all_records):,} addresses in {time.time()-t0:.2f}s")

    df = pd.DataFrame(all_records)
    conn = duckdb.connect()
    conn.register("df_county", df)
    conn.execute(f"COPY (SELECT * FROM df_county WHERE longitude IS NOT NULL AND latitude IS NOT NULL) TO '{output_parquet}' (FORMAT PARQUET)")
    print(f"  -> Saved {len(df):,} records to {output_parquet}")
    return len(df)

def fetch_fresno_county_streets():
    output_parquet = os.path.join(CACHE_DIR, "county_streets.parquet")
    print(f"\n[2/6] Fetching all Fresno County street centerlines from ArcGIS FeatureServer...")

    base_url = "https://services3.arcgis.com/ibgDyuD2DLBge82s/arcgis/rest/services/REGIONAL_STREETS_VW/FeatureServer/1/query"
    req = urllib.request.Request(
        f"{base_url}?where=STR_NAME+IS+NOT+NULL&returnCountOnly=true&f=json",
        headers={"User-Agent": "Fresno-NG911/1.0"}
    )
    with urllib.request.urlopen(req) as resp:
        total_count = json.loads(resp.read().decode("utf-8"))["count"]
    print(f"  Target record count: {total_count:,} streets")

    offsets = list(range(0, total_count, 2000))

    def fetch_page(offset):
        params = {
            "where": "STR_NAME IS NOT NULL",
            "outFields": "OBJECTID,STR_ID,STR_SEG,AGENCY_CODE,STR_DIR,STR_NAME,STR_TYPE,STR_POST_DIR,DS_REGIONAL_TYPE",
            "outSR": "4326",
            "resultOffset": offset,
            "resultRecordCount": 2000,
            "f": "geojson"
        }
        full_url = f"{base_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(full_url, headers={"User-Agent": "Fresno-NG911/1.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            records = []
            for f in data.get("features", []):
                props = f.get("properties", {})
                geom = f.get("geometry", {})
                records.append({
                    "street_segment_id": str(props.get("OBJECTID")),
                    "str_id": str(props.get("STR_ID") or ""),
                    "agency_code": str(props.get("AGENCY_CODE") or "FR"),
                    "pre_directional": props.get("STR_DIR"),
                    "street_name": props.get("STR_NAME"),
                    "street_type": props.get("STR_TYPE"),
                    "post_directional": props.get("STR_POST_DIR"),
                    "road_class": props.get("DS_REGIONAL_TYPE") or "Local",
                    "geom_geojson": json.dumps(geom)
                })
            return records

    t0 = time.time()
    all_records = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for batch in ex.map(fetch_page, offsets):
            all_records.extend(batch)
    print(f"  Retrieved {len(all_records):,} streets in {time.time()-t0:.2f}s")

    df = pd.DataFrame(all_records)
    conn = duckdb.connect()
    conn.sql("INSTALL spatial; LOAD spatial;")
    conn.register("df_streets", df)
    conn.execute(f"""
        COPY (
            SELECT 
                street_segment_id,
                str_id,
                agency_code,
                pre_directional,
                street_name,
                street_type,
                post_directional,
                road_class,
                ST_GeomFromGeoJSON(geom_geojson) AS geom
            FROM df_streets
            WHERE geom_geojson != '{{}}'
        ) TO '{output_parquet}' (FORMAT PARQUET)
    """)
    print(f"  -> Saved {len(df):,} centerlines to {output_parquet}")
    return len(df)

def fetch_fresno_county_boundaries():
    print("\n[3/6] Fetching Fresno County CAD/PSAP, Fire, and City Limits boundaries...")
    conn = duckdb.connect()
    conn.sql("INSTALL spatial; LOAD spatial;")
    
    layers = [
        ("CAD/PSAP", "https://services3.arcgis.com/ibgDyuD2DLBge82s/arcgis/rest/services/City_County_CAD/FeatureServer/78/query?where=1%3D1&outFields=*&outSR=4326&f=geojson", "county_cad_psap.parquet"),
        ("Fire Districts", "https://services3.arcgis.com/ibgDyuD2DLBge82s/arcgis/rest/services/ELECTIONS_FIRE_DISTRICTS_VW/FeatureServer/41/query?where=1%3D1&outFields=*&outSR=4326&f=geojson", "county_fire_districts.parquet"),
        ("City Limits", "https://services3.arcgis.com/ibgDyuD2DLBge82s/arcgis/rest/services/REGIONAL_CITY_LIMITS_VW/FeatureServer/1/query?where=1%3D1&outFields=*&outSR=4326&f=geojson", "county_city_limits.parquet")
    ]
    counts = {}
    for name, url, fname in layers:
        out_parquet = os.path.join(CACHE_DIR, fname)
        req = urllib.request.Request(url, headers={"User-Agent": "Fresno-NG911/1.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            features = data.get("features", [])
            records = []
            for f in features:
                props = f.get("properties", {})
                geom = f.get("geometry", {})
                props["geom_geojson"] = json.dumps(geom)
                records.append(props)
            df = pd.DataFrame(records)
            conn.register("df_layer", df)
            conn.execute(f"""
                COPY (
                    SELECT * EXCLUDE (geom_geojson), ST_GeomFromGeoJSON(geom_geojson) AS geom
                    FROM df_layer
                ) TO '{out_parquet}' (FORMAT PARQUET)
            """)
            print(f"  -> Saved {len(df)} {name} features to {out_parquet}")
            counts[name] = len(df)
    return counts

def fetch_overture_addresses():
    output_parquet = os.path.join(CACHE_DIR, "overture_addresses.parquet")
    print(f"\n[4/6] Fetching Overture Maps addresses for Fresno County extent...")
    conn = duckdb.connect()
    conn.execute("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    
    query = f"""
    COPY (
        SELECT
            id AS overture_id,
            geometry AS overture_geom,
            number AS overture_number,
            street AS overture_street,
            postcode AS overture_postcode,
            postal_city AS overture_city,
            bbox.xmin AS minx,
            bbox.xmax AS maxx,
            bbox.ymin AS miny,
            bbox.ymax AS maxy
        FROM read_parquet('s3://overturemaps-us-west-2/release/2026-09-23.1/theme=addresses/type=address/*.parquet')
        WHERE bbox.xmin >= {FRESNO_COUNTY_BBOX['minx']} AND bbox.xmax <= {FRESNO_COUNTY_BBOX['maxx']}
          AND bbox.ymin >= {FRESNO_COUNTY_BBOX['miny']} AND bbox.ymax <= {FRESNO_COUNTY_BBOX['maxy']}
        LIMIT 100000
    ) TO '{output_parquet}' (FORMAT PARQUET);
    """
    conn.execute(query)
    count = conn.execute(f"SELECT count(*) FROM read_parquet('{output_parquet}')").fetchone()[0]
    print(f"  -> Saved {count:,} Overture address records to {output_parquet}")
    return count

def fetch_overture_transportation():
    output_parquet = os.path.join(CACHE_DIR, "overture_transportation.parquet")
    print(f"\n[5/6] Fetching Overture Maps road segments for Fresno County extent...")
    conn = duckdb.connect()
    conn.execute("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")

    query = f"""
    COPY (
        SELECT
            id AS overture_segment_id,
            names.primary AS road_name,
            class AS road_class,
            subtype AS road_subtype,
            geometry AS geom,
            bbox.xmin AS minx,
            bbox.xmax AS maxx,
            bbox.ymin AS miny,
            bbox.ymax AS maxy
        FROM read_parquet('s3://overturemaps-us-west-2/release/2026-09-23.1/theme=transportation/type=segment/*.parquet')
        WHERE bbox.xmin >= {FRESNO_COUNTY_BBOX['minx']} AND bbox.xmax <= {FRESNO_COUNTY_BBOX['maxx']}
          AND bbox.ymin >= {FRESNO_COUNTY_BBOX['miny']} AND bbox.ymax <= {FRESNO_COUNTY_BBOX['maxy']}
        LIMIT 50000
    ) TO '{output_parquet}' (FORMAT PARQUET);
    """
    conn.execute(query)
    count = conn.execute(f"SELECT count(*) FROM read_parquet('{output_parquet}')").fetchone()[0]
    print(f"  -> Saved {count:,} Overture transportation segments to {output_parquet}")
    return count

def fetch_overture_places():
    output_parquet = os.path.join(CACHE_DIR, "overture_places.parquet")
    print(f"\n[6/6] Fetching Overture Places (Landmarks/POIs) for Fresno County extent...")
    conn = duckdb.connect()
    conn.execute("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    
    query = f"""
    COPY (
        SELECT
            id AS place_id,
            names.primary AS place_name,
            basic_category,
            taxonomy.primary AS taxonomy_category,
            confidence,
            geometry AS geom,
            ST_X(geometry) AS longitude,
            ST_Y(geometry) AS latitude
        FROM read_parquet('s3://overturemaps-us-west-2/release/2026-09-23.1/theme=places/type=place/*.parquet')
        WHERE bbox.xmin >= {FRESNO_COUNTY_BBOX['minx']} AND bbox.xmax <= {FRESNO_COUNTY_BBOX['maxx']}
          AND bbox.ymin >= {FRESNO_COUNTY_BBOX['miny']} AND bbox.ymax <= {FRESNO_COUNTY_BBOX['maxy']}
          AND (
            basic_category IN ('hospital', 'school', 'emergency_service', 'college_or_university', 'airport', 'library', 'fire_station', 'police_station')
            OR taxonomy.primary LIKE '%hospital%' 
            OR taxonomy.primary LIKE '%school%'
            OR taxonomy.primary LIKE '%fire%'
            OR taxonomy.primary LIKE '%police%'
            OR taxonomy.primary LIKE '%clinic%'
            OR taxonomy.primary LIKE '%airport%'
          )
    ) TO '{output_parquet}' (FORMAT PARQUET);
    """
    conn.execute(query)
    count = conn.execute(f"SELECT count(*) FROM read_parquet('{output_parquet}')").fetchone()[0]
    print(f"  -> Saved {count:,} Overture Places records to {output_parquet}")
    return count

if __name__ == "__main__":
    county_addr_cnt = fetch_fresno_county_addresses()
    county_street_cnt = fetch_fresno_county_streets()
    boundary_counts = fetch_fresno_county_boundaries()
    overture_addr_cnt = fetch_overture_addresses()
    overture_trans_cnt = fetch_overture_transportation()
    places_cnt = fetch_overture_places()
    print("\n" + "=" * 70)
    print("All Fresno County datasets cached successfully:")
    print(f"  - Fresno County Addresses:      {county_addr_cnt:,}")
    print(f"  - Fresno County Streets:        {county_street_cnt:,}")
    print(f"  - County CAD / PSAP:           {boundary_counts.get('CAD/PSAP', 0):,}")
    print(f"  - County Fire Districts:       {boundary_counts.get('Fire Districts', 0):,}")
    print(f"  - County City Limits:          {boundary_counts.get('City Limits', 0):,}")
    print(f"  - Overture Addresses:          {overture_addr_cnt:,}")
    print(f"  - Overture Road Segments:       {overture_trans_cnt:,}")
    print(f"  - Overture Places (Landmarks):  {places_cnt:,}")
    print("=" * 70)
