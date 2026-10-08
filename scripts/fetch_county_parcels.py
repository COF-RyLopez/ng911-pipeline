#!/usr/bin/env python3
"""
fetch_county_parcels.py
Fetches authoritative Fresno County cadastral tax parcels from ArcGIS REST:
https://services3.arcgis.com/ibgDyuD2DLBge82s/ArcGIS/rest/services/REGIONAL_PARCELS_VW/FeatureServer/11
Outputs cached Parquet file: data/cache/county_parcels.parquet
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import duckdb

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
OUTPUT_PARQUET = os.path.join(CACHE_DIR, "county_parcels.parquet")
SERVICE_URL = "https://services3.arcgis.com/ibgDyuD2DLBge82s/ArcGIS/rest/services/REGIONAL_PARCELS_VW/FeatureServer/11/query"

# Default to metro Fresno / Clovis extent or full county
# Metro BBOX: [-119.95, 36.65, -119.60, 36.95]
METRO_BBOX = "-119.95,36.65,-119.60,36.95"

def fetch_parcels(bbox=METRO_BBOX, max_records=15000):
    os.makedirs(CACHE_DIR, exist_ok=True)
    print("=" * 70)
    print("Fetching Fresno County Authoritative Tax Parcels (Layer 11)")
    print(f"Service URL: {SERVICE_URL}")
    print(f"Bounding Box: {bbox}")
    print("=" * 70)

    # 1. Check total count
    count_params = {
        "where": "1=1",
        "geometry": bbox,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "returnCountOnly": "true",
        "f": "json"
    }
    req = urllib.request.Request(
        f"{SERVICE_URL}?{urllib.parse.urlencode(count_params)}",
        headers={"User-Agent": "Fresno-NG911/1.0"}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        total_available = res.get("count", 0)
    
    print(f"Total parcels intersecting extent: {total_available:,}")
    limit = min(total_available, max_records)
    batch_size = 1000
    print(f"Fetching {limit:,} parcel polygons (batches of {batch_size})...")

    offsets = list(range(0, limit, batch_size))
    all_features = []

    def fetch_page(offset):
        params = {
            "where": "1=1",
            "geometry": bbox,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "OBJECTID,APN,AGENCY_CODE,ROLL_YEAR",
            "outSR": "4326",
            "resultOffset": offset,
            "resultRecordCount": batch_size,
            "f": "geojson"
        }
        url = f"{SERVICE_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Fresno-NG911/1.0"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    data = json.loads(resp.read().decode())
                    features = data.get("features", [])
                    print(f"  Offset {offset:6d}: received {len(features)} parcels")
                    return features
            except Exception as e:
                print(f"  Offset {offset:6d} retry {attempt+1}: {e}")
                time.sleep(2.0)
        return []

    with ThreadPoolExecutor(max_workers=3) as ex:
        for batch in ex.map(fetch_page, offsets):
            all_features.extend(batch)

    print(f"\nTotal raw parcel features fetched: {len(all_features):,}")
    if not all_features:
        print("No parcel features retrieved.")
        return

    # Process and write to DuckDB GeoParquet
    print(f"Converting GeoJSON to DuckDB geometry and saving to {OUTPUT_PARQUET}...")
    temp_json = os.path.join(CACHE_DIR, "parcels_temp.jsonl")
    with open(temp_json, "w") as f:
        for feat in all_features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            if not geom or not geom.get("coordinates"):
                continue
            row = {
                "parcel_id": props.get("OBJECTID"),
                "apn": str(props.get("APN") or ""),
                "agency_code": str(props.get("AGENCY_CODE") or ""),
                "roll_year": str(props.get("ROLL_YEAR") or ""),
                "geom_json": json.dumps(geom)
            }
            f.write(json.dumps(row) + "\n")

    conn = duckdb.connect()
    conn.execute("INSTALL spatial; LOAD spatial;")

    conn.execute(f"""
        CREATE TABLE parcels_clean AS
        SELECT
            parcel_id,
            apn,
            agency_code,
            roll_year,
            ST_GeomFromGeoJSON(geom_json) AS geom
        FROM read_json_auto('{temp_json}')
        WHERE geom_json IS NOT NULL;
    """)

    conn.execute(f"COPY parcels_clean TO '{OUTPUT_PARQUET}' (FORMAT PARQUET);")
    count = conn.execute("SELECT count(*) FROM parcels_clean").fetchone()[0]
    print(f"Successfully cached {count:,} parcel polygons to {OUTPUT_PARQUET}!")
    if os.path.exists(temp_json):
        os.remove(temp_json)

if __name__ == "__main__":
    max_rec = int(sys.argv[1]) if len(sys.argv) > 1 else 30000
    fetch_parcels(max_records=max_rec)
