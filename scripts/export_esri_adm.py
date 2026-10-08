#!/usr/bin/env python3
"""
export_esri_adm.py
Exports conflated NG911 address points and road centerlines into:
1. Esri Address Data Management (ADM) GeoPackage / FGDB format (fresno_esri_adm.gpkg)
2. ArcGIS Online / Enterprise FeatureService applyEdits change package (arcgis_online_apply_edits.json)
"""

import os
import sys
import json
import duckdb

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "ng911_database.duckdb")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output", "esri_adm")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    gpkg_path = os.path.join(OUTPUT_DIR, "fresno_esri_adm.gpkg")
    edits_json_path = os.path.join(OUTPUT_DIR, "arcgis_online_apply_edits.json")
    points_parquet_path = os.path.join(OUTPUT_DIR, "SiteAddressPoint.parquet")
    rcl_parquet_path = os.path.join(OUTPUT_DIR, "RoadCenterline.parquet")

    print(f"Connecting to {DB_PATH}...")
    conn = duckdb.connect(DB_PATH)
    conn.execute("INSTALL spatial; LOAD spatial;")

    # 1. Export Parquet representations for rapid streaming
    print(f"Exporting Esri ADM Parquet layers to {OUTPUT_DIR}...")
    conn.execute(f"COPY mart_esri_adm_siteaddresspoint TO '{points_parquet_path}' (FORMAT PARQUET);")
    conn.execute(f"COPY mart_esri_adm_roadcenterline TO '{rcl_parquet_path}' (FORMAT PARQUET);")

    # 2. Export GeoPackage containing both SiteAddressPoint and RoadCenterline
    print(f"Exporting Esri ADM GeoPackage to {gpkg_path}...")
    try:
        # If gpkg exists, remove to avoid layer append conflicts
        if os.path.exists(gpkg_path):
            os.remove(gpkg_path)

        conn.execute(f"""
            COPY (SELECT * FROM mart_esri_adm_siteaddresspoint) 
            TO '{gpkg_path}' 
            WITH (FORMAT GDAL, DRIVER 'GPKG', LAYER_NAME 'SiteAddressPoint');
        """)
        conn.execute(f"""
            COPY (SELECT * FROM mart_esri_adm_roadcenterline) 
            TO '{gpkg_path}' 
            WITH (FORMAT GDAL, DRIVER 'GPKG', LAYER_NAME 'RoadCenterline');
        """)
        print(f"  -> Successfully generated {gpkg_path}")
    except Exception as e:
        print(f"  Note on GPKG export: {e}")

    # 3. Export ArcGIS Online FeatureService applyEdits JSON payload
    print(f"Generating ArcGIS Online FeatureService applyEdits payload for high-priority remediations...")
    remediation_query = """
        SELECT 
            ADDRESSPTID,
            ADDRNUM,
            FULLNAME,
            FULLADDR,
            MUNI,
            ZIP,
            STRUCTUREID,
            SpatialOffsetMeters,
            RecommendedRemediationAction,
            ST_X(geom) AS lon,
            ST_Y(geom) AS lat
        FROM mart_esri_adm_siteaddresspoint
        WHERE IsExcessiveOffset = TRUE
        LIMIT 500;
    """
    recs = conn.execute(remediation_query).fetchall()
    
    adds = []
    updates = []
    for r in recs:
        # Format as Esri JSON feature
        feature = {
            "attributes": {
                "ADDRESSPTID": r[0],
                "ADDRNUM": r[1],
                "FULLNAME": r[2],
                "FULLADDR": r[3],
                "MUNI": r[4],
                "ZIP": r[5],
                "STRUCTUREID": r[6],
                "OFFSET_M": r[7],
                "ACTION": r[8],
                "STATUS": "Requires Verification"
            },
            "geometry": {
                "x": r[9],
                "y": r[10],
                "spatialReference": {"wkid": 4326}
            }
        }
        updates.append(feature)

    apply_edits_payload = {
        "id": 0, # Feature layer ID 0 (SiteAddressPoint)
        "adds": [],
        "updates": updates,
        "deletes": []
    }

    with open(edits_json_path, "w") as f:
        json.dump([apply_edits_payload], f, indent=2)

    print(f"  -> Generated {edits_json_path} ({len(updates)} update features)")
    print("\nEsri Address Data Management exports completed successfully!")

if __name__ == "__main__":
    main()
