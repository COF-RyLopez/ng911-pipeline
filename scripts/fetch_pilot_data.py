#!/usr/bin/env python3
"""
scripts/fetch_pilot_data.py

Ingests and caches authoritative geospatial data for Fresno County NG911:
1. Ingests Fresno County Site/Structure Address Points (REGIONAL_ADDRESS_VW/FeatureServer/1).
2. Ingests road centerlines for Fresno, Kings and Tulare from OpenAddresses' processed county sources.
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
from fetch_county_parcels import fetch_parcels
import fetch_mapillary_coverage
import county_config

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Overture reference data is fetched once for the extent of every county in the registry
# (dbt_project.yml `counties`), so any registered county can be built from the same cache.
_minx, _miny, _maxx, _maxy = county_config.union_bbox()
OVERTURE_BBOX = {"minx": _minx, "maxx": _maxx, "miny": _miny, "maxy": _maxy}

def fetch_fresno_county_addresses():
    output_parquet = os.path.join(CACHE_DIR, "county_addresses.parquet")
    print(f"\n[1/6] Fetching all Fresno County addresses from ArcGIS FeatureServer...")
    
    base_url = "https://services3.arcgis.com/ibgDyuD2DLBge82s/arcgis/rest/services/REGIONAL_ADDRESS_VW/FeatureServer/1/query"
    where_filter = "(ADDRESS_STATUS IN ('ACTIVE', 'C', 'PENDING', 'P') OR ADDRESS_STATUS IS NULL) AND ADDRESS_NUMBER IS NOT NULL"
    req = urllib.request.Request(
        f"{base_url}?where={urllib.parse.quote(where_filter)}&returnCountOnly=true&f=json",
        headers={"User-Agent": "Fresno-NG911/1.0"}
    )
    with urllib.request.urlopen(req) as resp:
        total_count = json.loads(resp.read().decode("utf-8"))["count"]
    print(f"  Target record count (Active + Current + Pending): {total_count:,} addresses")

    offsets = list(range(0, total_count, 2000))

    def fetch_page(offset):
        params = {
            "where": where_filter,
            "outFields": "OBJECTID,ADDRESS_NUMBER,ADDRESS_FRACTION,STREET_DIRECTION,STREET_NAME,STREET_TYPE,STREET_POST_DIRECTION,ADDRESS_UNIT,ADDRESS_ZIP5,ADDRESS_ZIPCITY,AGENCY_NAME,AGENCY_CODE,ADDRESS_STATUS",
            "orderByFields": "OBJECTID",
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
                agency_code = attr.get("AGENCY_CODE")
                source_agency = attr.get("AGENCY_NAME") or (
                    "City of Fresno" if agency_code == "FR" else (
                        "City of Clovis" if agency_code == "CL" else "County of Fresno"
                    )
                )
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
                    "source_agency": source_agency,
                    "address_status": attr.get("ADDRESS_STATUS") or "ACTIVE"
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


def fetch_kings_county_addresses():
    output_parquet = os.path.join(CACHE_DIR, "kings_addresses.parquet")
    print(f"\n[1b] Fetching Kings County addresses from ArcGIS FeatureServer...")
    try:
        url = "https://services3.arcgis.com/24gLq1DBBzDfd0cZ/ArcGIS/rest/services/Address_Kings_County/FeatureServer/4/query"
        req = urllib.request.Request(f"{url}?where=STREET_NBR+IS+NOT+NULL&returnCountOnly=true&f=json", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            total_count = json.loads(resp.read().decode("utf-8"))["count"]

        offsets = list(range(0, total_count, 2000))

        def fetch_page(offset):
            params = {
                "where": "STREET_NBR IS NOT NULL",
                "outFields": "GlobalID,STREET_NBR,STREET_DIR,STREET_NAM,STREET_TYP,COMMUNITY,ZIPCODE",
                "orderByFields": "OBJECTID_1",  # layer OID; stable paging
                "outSR": "4326",
                "resultOffset": offset,
                "resultRecordCount": 2000,
                "f": "json"
            }
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                records = []
                for feat in data.get("features", []):
                    attr = feat.get("attributes", {})
                    geom = feat.get("geometry", {})
                    records.append({
                        # ponytail: OBJECTID here is a stale non-unique attribute (OID is OBJECTID_1); GlobalID survives republish
                        "county_id": attr["GlobalID"].strip("{}").lower(),
                        "house_number": str(attr.get("STREET_NBR") or ""),
                        "pre_directional": attr.get("STREET_DIR"),
                        "street_name": attr.get("STREET_NAM"),
                        "street_type": attr.get("STREET_TYP"),
                        "community_name": attr.get("COMMUNITY"),
                        "postcode": str(attr.get("ZIPCODE") or ""),
                        "longitude": float(geom.get("x")) if geom.get("x") is not None else None,
                        "latitude": float(geom.get("y")) if geom.get("y") is not None else None,
                    })
                return records

        t0 = time.time()
        all_records = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            for batch in ex.map(fetch_page, offsets):
                all_records.extend(batch)
        print(f"  Retrieved {len(all_records):,} Kings addresses in {time.time()-t0:.2f}s")
        df = pd.DataFrame(all_records)
    except Exception as e:
        print(f"  [WARNING] Could not fetch Kings addresses online: {e}. Using empty stub.")
        df = pd.DataFrame(columns=["county_id", "house_number", "pre_directional", "street_name", "street_type", "community_name", "postcode", "longitude", "latitude"])

    conn = duckdb.connect()
    conn.register("df_kings", df)
    conn.execute(f"COPY (SELECT * FROM df_kings WHERE longitude IS NOT NULL AND latitude IS NOT NULL) TO '{output_parquet}' (FORMAT PARQUET)")
    print(f"  -> Saved {len(df):,} Kings records to {output_parquet}")
    return len(df)


def fetch_tulare_county_addresses():
    output_parquet = os.path.join(CACHE_DIR, "tulare_addresses.parquet")
    print(f"\n[1c] Fetching Tulare County addresses from ArcGIS FeatureServer...")
    try:
        url = "https://services2.arcgis.com/bYBANhmQGwSSLC0l/ArcGIS/rest/services/SiteStructureAddressPoints/FeatureServer/0/query"
        req = urllib.request.Request(f"{url}?where=Add_Number+IS+NOT+NULL&returnCountOnly=true&f=json", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            total_count = json.loads(resp.read().decode("utf-8"))["count"]

        offsets = list(range(0, total_count, 2000))

        def fetch_page(offset):
            params = {
                "where": "Add_Number IS NOT NULL",
                "outFields": "OBJECTID,Add_Number,AddNum_Suf,St_PreDir,St_Name,St_PosTyp,LSt_Typ,Post_Comm,Post_Code,Longitude,Latitude",
                "orderByFields": "OBJECTID",
                "outSR": "4326",
                "resultOffset": offset,
                "resultRecordCount": 2000,
                "f": "json"
            }
            full_url = f"{url}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                records = []
                for feat in data.get("features", []):
                    attr = feat.get("attributes", {})
                    geom = feat.get("geometry", {})
                    lon = attr.get("Longitude") or (float(geom.get("x")) if geom.get("x") is not None else None)
                    lat = attr.get("Latitude") or (float(geom.get("y")) if geom.get("y") is not None else None)
                    records.append({
                        "county_id": str(attr.get("OBJECTID")),
                        "house_number": str(attr.get("Add_Number") or ""),
                        "house_number_suffix": attr.get("AddNum_Suf"),
                        "pre_directional": attr.get("St_PreDir"),
                        "street_name": attr.get("St_Name"),
                        "street_type": attr.get("St_PosTyp") or attr.get("LSt_Typ"),
                        "community_name": attr.get("Post_Comm"),
                        "postcode": str(attr.get("Post_Code") or ""),
                        "longitude": float(lon) if lon is not None else None,
                        "latitude": float(lat) if lat is not None else None,
                    })
                return records

        t0 = time.time()
        all_records = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            for batch in ex.map(fetch_page, offsets):
                all_records.extend(batch)
        print(f"  Retrieved {len(all_records):,} Tulare addresses in {time.time()-t0:.2f}s")
        df = pd.DataFrame(all_records)
    except Exception as e:
        print(f"  [WARNING] Could not fetch Tulare addresses online: {e}. Using empty stub.")
        df = pd.DataFrame(columns=["county_id", "house_number", "house_number_suffix", "pre_directional", "street_name", "street_type", "community_name", "postcode", "longitude", "latitude"])

    conn = duckdb.connect()
    conn.register("df_tulare", df)
    conn.execute(f"COPY (SELECT * FROM df_tulare WHERE longitude IS NOT NULL AND latitude IS NOT NULL) TO '{output_parquet}' (FORMAT PARQUET)")
    print(f"  -> Saved {len(df):,} Tulare records to {output_parquet}")
    return len(df)


# Road centerlines come from OpenAddresses' processed output for each county
# (sources/us/ca/<county>.json -> centerlines). OpenAddresses re-runs the county
# endpoints on a schedule, so we download one gzip per county instead of
# paginating each county ArcGIS server ourselves.
OA_CENTERLINE_SOURCES = {"fresno": "FRESNO", "kings": "KINGS", "tulare": "TULARE"}
OA_API = "https://batch.openaddresses.io/api"
OA_FIELDS = ["id", "name", "classification", "oneway", "speed",
             "addr_from_left", "addr_to_left", "addr_from_right", "addr_to_right",
             "zip_left", "zip_right"]


def _oa_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Fresno-NG911/1.0"})
    return urllib.request.urlopen(req, timeout=120)


def fetch_oa_centerlines():
    import gzip
    output_parquet = os.path.join(CACHE_DIR, "oa_centerlines.parquet")
    print(f"\n[2/6] Fetching road centerlines from OpenAddresses ({', '.join(OA_CENTERLINE_SOURCES)})...")
    records = []
    for src, county in OA_CENTERLINE_SOURCES.items():
        with _oa_get(f"{OA_API}/data?source=us/ca/{src}") as r:
            entry = next(d for d in json.load(r) if d["layer"] == "centerlines")
        url = f"https://v2.openaddresses.io/batch-prod/job/{entry['job']}/source.geojson.gz"
        n = 0
        with _oa_get(url) as r, gzip.open(r, "rt") as lines:
            for line in lines:
                if not line.strip():
                    continue
                f = json.loads(line)
                p = f.get("properties") or {}
                rec = {k: (p.get(k) or None) for k in OA_FIELDS}
                rec.update(county_name=county, oa_source=f"us/ca/{src}", oa_job=entry["job"],
                           oa_hash=p.get("hash"), geom_geojson=json.dumps(f.get("geometry")))
                records.append(rec)
                n += 1
        print(f"  us/ca/{src}: {n:,} segments (OA job {entry['job']}, updated {entry['updated'][:10]})")

    df = pd.DataFrame(records)
    conn = duckdb.connect()
    conn.sql("INSTALL spatial; LOAD spatial;")
    conn.register("df_cl", df)
    conn.execute(f"""
        COPY (
            SELECT * EXCLUDE (geom_geojson), ST_GeomFromGeoJSON(geom_geojson) AS geom
            FROM df_cl WHERE geom_geojson NOT IN ('null', '{{}}')
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
    print(f"\n[4/6] Fetching Overture Maps addresses for the registered counties' extent...")
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
        WHERE bbox.xmin >= {OVERTURE_BBOX['minx']} AND bbox.xmax <= {OVERTURE_BBOX['maxx']}
          AND bbox.ymin >= {OVERTURE_BBOX['miny']} AND bbox.ymax <= {OVERTURE_BBOX['maxy']}
    ) TO '{output_parquet}' (FORMAT PARQUET);
    """
    conn.execute(query)
    count = conn.execute(f"SELECT count(*) FROM read_parquet('{output_parquet}')").fetchone()[0]
    print(f"  -> Saved {count:,} Overture address records to {output_parquet}")
    return count

def fetch_overture_transportation():
    output_parquet = os.path.join(CACHE_DIR, "overture_transportation.parquet")
    print(f"\n[5/6] Fetching Overture Maps road segments for the registered counties' extent...")
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
        WHERE bbox.xmin >= {OVERTURE_BBOX['minx']} AND bbox.xmax <= {OVERTURE_BBOX['maxx']}
          AND bbox.ymin >= {OVERTURE_BBOX['miny']} AND bbox.ymax <= {OVERTURE_BBOX['maxy']}
    ) TO '{output_parquet}' (FORMAT PARQUET);
    """
    conn.execute(query)
    count = conn.execute(f"SELECT count(*) FROM read_parquet('{output_parquet}')").fetchone()[0]
    print(f"  -> Saved {count:,} Overture transportation segments to {output_parquet}")
    return count

def fetch_overture_divisions():
    """County and city (locality) polygons from Overture's divisions theme, for the Overture-only build."""
    output_parquet = os.path.join(CACHE_DIR, "overture_divisions.parquet")
    print(f"\n[Divisions] Fetching Overture county and city boundaries for the registered counties' extent...")
    conn = duckdb.connect()
    conn.execute("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    conn.execute(f"""
    COPY (
        SELECT
            id AS division_area_id,
            division_id,
            names.primary AS name,
            subtype,
            class,
            geometry AS geom
        FROM read_parquet('s3://overturemaps-us-west-2/release/2026-09-23.1/theme=divisions/type=division_area/*.parquet')
        WHERE country = 'US' AND region = 'US-CA' AND subtype IN ('county', 'locality')
          -- overlap, not containment: counties extend past each other's boxes
          AND bbox.xmax >= {OVERTURE_BBOX['minx']} AND bbox.xmin <= {OVERTURE_BBOX['maxx']}
          AND bbox.ymax >= {OVERTURE_BBOX['miny']} AND bbox.ymin <= {OVERTURE_BBOX['maxy']}
    ) TO '{output_parquet}' (FORMAT PARQUET);
    """)
    count = conn.sql(f"SELECT count(*) FROM read_parquet('{output_parquet}')").fetchall()[0][0]
    print(f"  -> Saved {count:,} Overture division areas to {output_parquet}")
    return count

def fetch_overture_places():
    output_parquet = os.path.join(CACHE_DIR, "overture_places.parquet")
    print(f"\n[6/6] Fetching Overture Places (Landmarks/POIs) for the registered counties' extent...")
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
        WHERE bbox.xmin >= {OVERTURE_BBOX['minx']} AND bbox.xmax <= {OVERTURE_BBOX['maxx']}
          AND bbox.ymin >= {OVERTURE_BBOX['miny']} AND bbox.ymax <= {OVERTURE_BBOX['maxy']}
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

def fetch_overture_buildings():
    output_parquet = os.path.join(CACHE_DIR, "overture_buildings.parquet")
    print(f"\n[7/7] Fetching Overture Building Footprints for the registered counties' extent...")
    try:
        conn = duckdb.connect()
        conn.execute("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
        query = f"""
        COPY (
            SELECT
                id AS building_id,
                height,
                num_floors,
                class AS building_class,
                geometry AS geom
            FROM read_parquet('s3://overturemaps-us-west-2/release/2026-09-23.1/theme=buildings/type=building/*.parquet')
            WHERE bbox.xmin >= {OVERTURE_BBOX['minx']} AND bbox.xmax <= {OVERTURE_BBOX['maxx']}
              AND bbox.ymin >= {OVERTURE_BBOX['miny']} AND bbox.ymax <= {OVERTURE_BBOX['maxy']}
        ) TO '{output_parquet}' (FORMAT PARQUET);
        """
        conn.execute(query)
        count = conn.execute(f"SELECT count(*) FROM read_parquet('{output_parquet}')").fetchone()[0]
        print(f"  -> Saved {count:,} Overture Building footprints to {output_parquet}")
        return count
    except Exception as e:
        print(f"  [WARNING] Could not fetch Overture Buildings online: {e}. Using empty stub.")
        conn = duckdb.connect()
        conn.sql("INSTALL spatial; LOAD spatial;")
        conn.execute(f"COPY (SELECT NULL::VARCHAR AS building_id, NULL::DOUBLE AS height, NULL::INTEGER AS num_floors, NULL::VARCHAR AS building_class, ST_GeomFromText('POLYGON EMPTY') AS geom WHERE 1=0) TO '{output_parquet}' (FORMAT PARQUET)")
        return 0


if __name__ == "__main__":
    county_addr_cnt = fetch_fresno_county_addresses()
    kings_addr_cnt = fetch_kings_county_addresses()
    tulare_addr_cnt = fetch_tulare_county_addresses()
    county_street_cnt = fetch_oa_centerlines()
    boundary_counts = fetch_fresno_county_boundaries()
    overture_addr_cnt = fetch_overture_addresses()
    overture_trans_cnt = fetch_overture_transportation()
    places_cnt = fetch_overture_places()
    divisions_cnt = fetch_overture_divisions()
    bldg_cnt = fetch_overture_buildings()
    parcel_cnt = fetch_parcels()
    try:
        mly_cnt = fetch_mapillary_coverage.fetch_mapillary_coverage()
    except Exception as e:  # advisory layer: don't fail the whole build when Mapillary is down
        print(f"  [WARNING] Mapillary coverage unavailable: {e}. Using empty stub.")
        fetch_mapillary_coverage.write_empty_stub()
        mly_cnt = 0
    print("\n" + "=" * 70)
    print("All Central Valley Region datasets cached successfully:")
    print(f"  - Fresno County Addresses:      {county_addr_cnt:,}")
    print(f"  - Kings County Addresses:       {kings_addr_cnt:,}")
    print(f"  - Tulare County Addresses:      {tulare_addr_cnt:,}")
    print(f"  - OA Road Centerlines:          {county_street_cnt:,}")
    print(f"  - County CAD / PSAP:           {boundary_counts.get('CAD/PSAP', 0):,}")
    print(f"  - County Fire Districts:       {boundary_counts.get('Fire Districts', 0):,}")
    print(f"  - County City Limits:          {boundary_counts.get('City Limits', 0):,}")
    print(f"  - Overture Addresses:          {overture_addr_cnt:,}")
    print(f"  - Overture Road Segments:       {overture_trans_cnt:,}")
    print(f"  - Overture Places (Landmarks):  {places_cnt:,}")
    print(f"  - Overture Division Areas:      {divisions_cnt:,}")
    print(f"  - Overture Building Footprints: {bldg_cnt:,}")
    print(f"  - County Parcels:               {parcel_cnt:,}")
    print(f"  - Mapillary Imagery Segments:   {mly_cnt:,}")
    print("=" * 70)


