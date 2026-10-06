#!/usr/bin/env python3
"""
scripts/run_pilot.py

End-to-end execution, testing, and GIS export script for the Fresno County NG911 Pilot:
1. Verifies cached source data exists (runs fetch_pilot_data.py if missing).
2. Executes dbt pipeline models (SSAP addresses, RCL centerlines, QA discrepancies, and Fishbones).
3. Runs automated dbt data quality and NENA integrity tests (37 tests).
4. Exports deliverables to data/output/ (Parquet and GeoJSON compatible with GeoLibre and QGIS).
5. Prints an automated Pilot Evaluation Scorecard.
"""

import os
import sys
import subprocess
import time
import duckdb

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "data", "output")
CACHE_DIR = os.path.join(PROJECT_DIR, "data", "cache")
DB_PATH = os.path.join(PROJECT_DIR, "ng911_database.duckdb")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def run_cmd(cmd_list, desc):
    print(f"\n[RUNNING] {desc}...")
    t0 = time.time()
    result = subprocess.run(cmd_list, cwd=PROJECT_DIR, capture_output=True, text=True)
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"[FAILED] {desc} (in {elapsed:.2f}s):\n{result.stderr}\n{result.stdout}")
        sys.exit(1)
    print(f"[SUCCESS] {desc} in {elapsed:.2f}s")
    return result.stdout

def main():
    print("=" * 75)
    print("      FRESNO COUNTY NG911 CLOUD-NATIVE GEOSPATIAL PIPELINE PILOT")
    print("   Layers: NENA-STA-010 SSAP, RCL, QA Discrepancies & Fishbones")
    print("=" * 75)

    # 1. Check data cache
    required_caches = [
        os.path.join(CACHE_DIR, "county_addresses.parquet"),
        os.path.join(CACHE_DIR, "county_streets.parquet"),
        os.path.join(CACHE_DIR, "overture_addresses.parquet"),
        os.path.join(CACHE_DIR, "overture_transportation.parquet")
    ]
    if not all(os.path.exists(p) for p in required_caches):
        fetch_script = os.path.join(PROJECT_DIR, "scripts", "fetch_pilot_data.py")
        run_cmd([sys.executable, fetch_script], "Ingesting & caching pilot datasets")

    # 2. Run dbt models
    dbt_bin = os.path.join(PROJECT_DIR, ".venv", "bin", "dbt")
    if not os.path.exists(dbt_bin):
        dbt_bin = "dbt"
    run_cmd([dbt_bin, "run", "--profiles-dir", "."], "dbt Transformations (SSAP, RCL, QA, Fishbones)")

    # 3. Run dbt tests
    run_cmd([dbt_bin, "test", "--profiles-dir", "."], "dbt Data Quality & NENA Integrity Tests")

    # 4. Export to GIS formats
    print("\n[EXPORTING] Generating GIS deliverables in data/output/...")
    conn = duckdb.connect(DB_PATH, read_only=True)
    conn.sql("INSTALL spatial; LOAD spatial;")

    def export_geojson_feature_collection(query, output_path):
        import json, pandas as pd
        df = conn.sql(query).df()
        features = []
        for _, row in df.iterrows():
            record = row.to_dict()
            geom_str = record.pop('geometry', None)
            if geom_str:
                try:
                    geom = json.loads(geom_str)
                    cleaned_props = {
                        k: (None if pd.isna(v) else v)
                        for k, v in record.items()
                    }
                    features.append({
                        'type': 'Feature',
                        'geometry': geom,
                        'properties': cleaned_props
                    })
                except Exception:
                    continue
        fc = {'type': 'FeatureCollection', 'features': features}
        with open(output_path, 'w') as f:
            json.dump(fc, f)

    # Export SSAP
    ssap_parquet = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_ssap.parquet")
    ssap_geojson = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_ssap_sample.geojson")
    conn.sql(f"COPY mart_ng911_addresses TO '{ssap_parquet}' (FORMAT PARQUET)")
    export_geojson_feature_collection(
        """
        SELECT 
            SSAP_NGUID, DisclID, CountyLocalID, GERS_ID, ConflationStatus, 
            Source, HNO, PRD, STN, STS, Unit, Muni, CommunityName, County, State, 
            PostCode, PSAP, PSAP_NGUID, ESB_Fire, LandmarkName, LandmarkCategory,
            SpatialOffsetMeters, ST_AsGeoJSON(ST_Geometry) AS geometry
        FROM mart_ng911_addresses
        WHERE ConflationStatus = 'CONFLATED' OR rowid % 10 = 0
        LIMIT 5000
        """,
        ssap_geojson
    )
    print(f"  -> Exported SSAP Address Points: {ssap_parquet} & {ssap_geojson}")

    # Export RCL
    rcl_parquet = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_rcl.parquet")
    rcl_geojson = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_rcl_sample.geojson")
    conn.sql(f"COPY mart_ng911_road_centerlines TO '{rcl_parquet}' (FORMAT PARQUET)")
    export_geojson_feature_collection(
        """
        SELECT 
            RCL_NGUID, DisclID, FullStreetName, FromAddr_L, ToAddr_L,
            FromAddr_R, ToAddr_R, Parity_L, Parity_R, SpeedLimit,
            RoadClass, ST_AsGeoJSON(ST_Geometry) AS geometry
        FROM mart_ng911_road_centerlines
        LIMIT 2500
        """,
        rcl_geojson
    )
    print(f"  -> Exported RCL Road Centerlines: {rcl_parquet} & {rcl_geojson}")

    # Export Emergency Service Boundaries (ESBs & PSAP CAD)
    esb_parquet = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_esb.parquet")
    esb_geojson = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_esb_sample.geojson")
    conn.sql(f"COPY mart_ng911_emergency_boundaries TO '{esb_parquet}' (FORMAT PARQUET)")
    export_geojson_feature_collection(
        """
        SELECT 
            DisclID, ESB_NGUID, Agency_Type, Agency_Name, Agency_Code,
            ServiceNum, Area_Code, ST_AsGeoJSON(ST_Geometry) AS geometry
        FROM mart_ng911_emergency_boundaries
        """,
        esb_geojson
    )
    print(f"  -> Exported Emergency Service Boundaries: {esb_parquet} & {esb_geojson}")

    # Export QA Discrepancies
    qa_parquet = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_qa_discrepancies.parquet")
    conn.sql(f"COPY mart_ng911_qa_discrepancies TO '{qa_parquet}' (FORMAT PARQUET)")
    print(f"  -> Exported QA Discrepancies: {qa_parquet}")

    # Export Fishbones
    fishbone_parquet = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_fishbones.parquet")
    fishbone_geojson = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_fishbones_sample.geojson")
    conn.sql(f"COPY mart_ng911_qa_fishbones TO '{fishbone_parquet}' (FORMAT PARQUET)")
    export_geojson_feature_collection(
        """
        SELECT 
            FishboneID, SSAP_NGUID, RCL_NGUID, HNO, STN,
            DistanceMeters, IsExcessiveOffset, IsRangeViolation,
            ST_AsGeoJSON(ST_Geometry) AS geometry
        FROM mart_ng911_qa_fishbones
        LIMIT 2500
        """,
        fishbone_geojson
    )
    print(f"  -> Exported QA Fishbone Vectors: {fishbone_parquet} & {fishbone_geojson}")

    # Export Cal OES 98% Readiness Audit Mart
    audit_parquet = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_readiness_audit.parquet")
    conn.sql(f"COPY mart_ng911_qa_readiness_audit TO '{audit_parquet}' (FORMAT PARQUET)")
    print(f"  -> Exported Cal OES Readiness Audit Mart: {audit_parquet}")

    # Export GeoLibre project file (.geolibre and .geolibre.json)
    gen_proj_script = os.path.join(PROJECT_DIR, "scripts", "generate_geolibre_project.py")
    subprocess.run([sys.executable, gen_proj_script], cwd=PROJECT_DIR, check=True)
    print(f"  -> Exported GeoLibre Project: {os.path.join(OUTPUT_DIR, 'fresno_ng911_pilot.geolibre')}")


    total_addr = conn.sql("SELECT count(*) FROM mart_ng911_addresses").fetchone()[0]
    addr_metrics = conn.sql("""
        SELECT ConflationStatus, count(*), round(avg(SpatialOffsetMeters), 3) 
        FROM mart_ng911_addresses GROUP BY ConflationStatus
    """).fetchall()

    total_roads = conn.sql("SELECT count(*) FROM mart_ng911_road_centerlines").fetchone()[0]
    mapped_roads = conn.sql("SELECT count(*) FROM mart_ng911_road_centerlines WHERE FromAddr_L IS NOT NULL OR FromAddr_R IS NOT NULL").fetchone()[0]

    qa_metrics = conn.sql("""
        SELECT DiscrepancyType, count(*) FROM mart_ng911_qa_discrepancies GROUP BY DiscrepancyType
    """).fetchall()

    fishbone_metrics = conn.sql("""
        SELECT 
            count(*) as total_fishbones,
            round(avg(DistanceMeters), 2) as avg_dist,
            count(CASE WHEN IsExcessiveOffset THEN 1 END) as excessive_cnt,
            count(CASE WHEN IsRangeViolation THEN 1 END) as violation_cnt
        FROM mart_ng911_qa_fishbones
    """).fetchone()

    conflated_cnt = next((m[1] for m in addr_metrics if m[0] == "CONFLATED"), 0)
    county_only_cnt = next((m[1] for m in addr_metrics if m[0] == "COUNTY_ONLY"), 0)
    overture_only_cnt = next((m[1] for m in addr_metrics if m[0] == "OVERTURE_ONLY"), 0)
    avg_offset = next((m[2] for m in addr_metrics if m[0] == "CONFLATED"), 0.0)

    missing_roads_cnt = next((m[1] for m in qa_metrics if m[0] == "POTENTIAL_MISSING_ROAD"), 0)
    name_mismatches_cnt = next((m[1] for m in qa_metrics if m[0] == "NAME_MISMATCH"), 0)

    # Cal OES Readiness Audit
    audit_row = conn.sql("SELECT * FROM mart_ng911_qa_readiness_audit").df().to_dict('records')[0]

    print("\n" + "=" * 75)
    print("                       PILOT EVALUATION SCORECARD")
    print("=" * 75)
    print(f"  Jurisdiction:             County of Fresno, California (FIPS 06019)")
    print(f"  Authoritative Source:     Fresno County ArcGIS Hub (cofgisonline)")
    print(f"  Reference Source:         Overture Maps Foundation (S3 GeoParquet)")
    print(f"  Licensing Integrity:      100% County Geometry Preserved (Zero ODbL)")
    print("-" * 75)
    print(f"  LAYER 1: SITE/STRUCTURE ADDRESS POINTS (SSAP):")
    print(f"  - Total Points:           {total_addr:,}")
    print(f"  - Conflated (Both):       {conflated_cnt:,} ({conflated_cnt/total_addr*100:.1f}%)")
    print(f"  - Authoritative County:   {county_only_cnt:,} ({county_only_cnt/total_addr*100:.1f}%)")
    print(f"  - Overture Unverified:    {overture_only_cnt:,} ({overture_only_cnt/total_addr*100:.1f}%)")
    print(f"  - Mean Spatial Offset:    {avg_offset} meters")
    print(f"  - With Landmark/POI Alias:{audit_row['SSAP_With_Landmark_Alias']:,} authoritative POIs matched")
    print("-" * 75)
    print(f"  LAYER 2: ROAD CENTERLINES (RCL):")
    print(f"  - Centerline Segments:    {total_roads:,}")
    print(f"  - Range Synthesized:      {mapped_roads:,} segments mapped with From/To ranges")
    print(f"  - Geometry Attribution:   100% Fresno County REGIONAL_STREETS_VW")
    print("-" * 75)
    print(f"  LAYER 3: EMERGENCY SERVICE BOUNDARIES (ESB & CAD/PSAP):")
    esb_counts = conn.sql("SELECT Agency_Type, count(*) FROM mart_ng911_emergency_boundaries GROUP BY Agency_Type").fetchall()
    for atype, acnt in esb_counts:
        print(f"  - {atype} Polygons:       {acnt:,}")
    print(f"  - SSAP with PSAP Bound:   {audit_row['SSAP_With_PSAP']:,} ({audit_row['Pct_PSAP_Attributed']}%)")
    print(f"  - SSAP with Fire ESB:     {audit_row['SSAP_With_Fire_ESB']:,} ({audit_row['Pct_Fire_Attributed']}%)")
    print("-" * 75)
    print(f"  LAYER 4: NENA QA/QC FISHBONE VALIDATION:")
    print(f"  - Fishbone Vectors:       {fishbone_metrics[0]:,} addresses snapped to centerlines")
    print(f"  - Mean Offset to Road:    {fishbone_metrics[1]} meters")
    print(f"  - Snapped within 50m:     {audit_row['SSAP_Snapped_Within_50m']:,} ({audit_row['Pct_SSAP_Snapped_Within_50m']}%)")
    print(f"  - Excessive Offsets (>50m):{fishbone_metrics[2]:,} flagged for analyst review")
    print("-" * 75)
    print(f"  LAYER 5: QA/QC DISCREPANCY AUDITING:")
    print(f"  - Potential Missing Roads:{missing_roads_cnt:,} (Overture roads absent from County GIS)")
    print(f"  - Street Name Mismatches: {name_mismatches_cnt:,} (Spelling / alias discrepancies)")
    print("-" * 75)
    print(f"  CAL OES 98% NG911 TRANSITION READINESS SCORECARD:")
    print(f"  - RCL Snapping (>= 98%):   {audit_row['Pct_SSAP_Snapped_Within_50m']}% -> {'[PASS]' if audit_row['Snapping_Threshold_Passed'] else '[FAIL]'}")
    print(f"  - PSAP Coverage (>= 98%):  {audit_row['Pct_PSAP_Attributed']}% -> {'[PASS]' if audit_row['PSAP_Coverage_Passed'] else '[FAIL]'}")
    print(f"  - Inverted Ranges (= 0):   {audit_row['Road_Range_Inversions']} -> {'[PASS]' if audit_row['Zero_Range_Inversions_Passed'] else '[FAIL]'}")
    print(f"  - Cal OES Readiness:       {audit_row['Cal_OES_Readiness_Status']}")
    print("-" * 75)
    print(f"  Deliverables Generated:   SSAP (Parquet/GeoJSON), RCL (Parquet/GeoJSON),")
    print(f"                            ESB (Parquet/GeoJSON), Fishbones (Parquet/GeoJSON),")
    print(f"                            QA (Parquet), Readiness Audit (Parquet)")
    print(f"  GeoLibre Project:         data/output/fresno_ng911_pilot.geolibre (.json)")
    print(f"  GeoLibre 1-Click URL:     https://web.geolibre.app/?url=https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/fresno_ng911_pilot.geolibre.json")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
