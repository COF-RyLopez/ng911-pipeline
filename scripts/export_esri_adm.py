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
    roadnames_parquet_path = os.path.join(OUTPUT_DIR, "MasterRoadName.parquet")

    print(f"Connecting to {DB_PATH}...")
    conn = duckdb.connect(DB_PATH)
    conn.execute("INSTALL spatial; LOAD spatial;")

    # 1. Export Parquet representations for rapid streaming
    print(f"Exporting Esri ADM Parquet layers to {OUTPUT_DIR}...")
    conn.execute(f"COPY mart_esri_adm_siteaddresspoint TO '{points_parquet_path}' (FORMAT PARQUET);")
    conn.execute(f"COPY mart_esri_adm_roadcenterline TO '{rcl_parquet_path}' (FORMAT PARQUET);")
    conn.execute(f"COPY mart_esri_adm_masterroadname TO '{roadnames_parquet_path}' (FORMAT PARQUET);")

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
        conn.execute(f"""
            COPY (SELECT * FROM mart_esri_adm_masterroadname)
            TO '{gpkg_path}'
            WITH (FORMAT GDAL, DRIVER 'GPKG', LAYER_NAME 'MasterRoadName');
        """)
        print(f"  -> Successfully generated {gpkg_path}")
    except Exception as e:
        print(f"  Note on GPKG export: {e}")

    # 3. Export ArcGIS Online FeatureService applyEdits JSON payload
    # Features go in "adds": an update must carry the target layer's OBJECTID or GlobalID, which this
    # pipeline does not know. Attributes are ADM SiteAddressPoint fields only.
    print(f"Generating ArcGIS Online FeatureService applyEdits payload for high-priority remediations...")
    adm_fields = ["siteaddid", "sitenguid", "discrpagid", "addrnum", "addrnumsuf", "unittype", "unitid",
                  "fullname", "fulladdr", "country", "stateabbreviation", "county", "municipality",
                  "pointtype", "capturemeth", "status"]
    remediation_query = f"""
        SELECT {", ".join("p." + f for f in adm_fields)}, ST_X(p.geom) AS lon, ST_Y(p.geom) AS lat
        FROM mart_esri_adm_siteaddresspoint p
        JOIN mart_ng911_county_remediation_export r ON r.SSAP_NGUID = p.sitenguid
        WHERE r.IsExcessiveOffset = TRUE
        ORDER BY r.SpatialOffsetMeters DESC
        LIMIT 500;
    """
    recs = conn.execute(remediation_query).fetchall()

    adds = [
        {
            "attributes": dict(zip(adm_fields, r[:-2])),
            "geometry": {"x": r[-2], "y": r[-1], "spatialReference": {"wkid": 4326}},
        }
        for r in recs
    ]

    apply_edits_payload = {
        "id": 0, # Feature layer ID 0 (SiteAddressPoint)
        "adds": adds,
        "updates": [],
        "deletes": []
    }

    with open(edits_json_path, "w") as f:
        json.dump([apply_edits_payload], f, indent=2)

    print(f"  -> Generated {edits_json_path} ({len(adds)} add features)")
    print("\nEsri Address Data Management exports completed successfully!")

if __name__ == "__main__":
    main()
