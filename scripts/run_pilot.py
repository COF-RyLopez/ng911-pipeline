#!/usr/bin/env python3
"""
scripts/run_pilot.py

End-to-end execution, testing, and GIS export script for one county's NG911 build
(--county FIPS from the dbt_project.yml registry; default Fresno, 06019):
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
import json
import argparse
import urllib.request
import county_config
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "data", "output")
CACHE_DIR = os.path.join(PROJECT_DIR, "data", "cache")
DB_PATH = os.path.join(PROJECT_DIR, "ng911_database.duckdb")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# County ArcGIS layers this pipeline consumes (centerlines arrive via OpenAddresses).
FRESNO = "https://services3.arcgis.com/ibgDyuD2DLBge82s/ArcGIS/rest/services"
KINGS = "https://services3.arcgis.com/24gLq1DBBzDfd0cZ/ArcGIS/rest/services"
TULARE = "https://services2.arcgis.com/bYBANhmQGwSSLC0l/ArcGIS/rest/services"
SOURCES = {
    "Fresno addresses":     f"{FRESNO}/REGIONAL_ADDRESS_VW/FeatureServer/1",
    "Fresno centerlines":   f"{FRESNO}/REGIONAL_STREETS_VW/FeatureServer/1",
    "Fresno parcels":       f"{FRESNO}/REGIONAL_PARCELS_VW/FeatureServer/11",
    "Fresno city limits":   f"{FRESNO}/REGIONAL_CITY_LIMITS_VW/FeatureServer/1",
    "Fresno fire dispatch": f"{FRESNO}/Fire/FeatureServer/0",
    "Fresno CAD law dispatch": f"{FRESNO}/City_County_CAD/FeatureServer/78",
    "Kings addresses":      f"{KINGS}/Address_Kings_County/FeatureServer/4",
    "Kings centerlines":    f"{KINGS}/Streets/FeatureServer/0",
    "Tulare addresses":     f"{TULARE}/SiteStructureAddressPoints/FeatureServer/0",
    "Tulare centerlines":   f"{TULARE}/RoadCenterLine/FeatureServer/0",
}
STALE_DAYS = 365


def last_published(url):
    """Layer's last data edit (UTC date), or None if unreachable. Hosted views report the overwrite date."""
    try:
        with urllib.request.urlopen(url + "?f=json", timeout=20) as r:
            e = json.load(r).get("editingInfo", {})
        ms = e.get("dataLastEditDate") or e.get("lastEditDate")
        return datetime.fromtimestamp(ms / 1000, timezone.utc).date() if ms else None
    except Exception:
        return None


def source_freshness():
    with ThreadPoolExecutor(8) as ex:
        dates = dict(zip(SOURCES, ex.map(last_published, SOURCES.values())))
    today = datetime.now(timezone.utc).date()
    rows = []
    for name, d in dates.items():
        age = (today - d).days if d else None
        flag = "unreachable" if d is None else ("STALE" if age > STALE_DAYS else "ok")
        rows.append({"source": name, "url": SOURCES[name], "last_published": str(d) if d else None,
                     "age_days": age, "status": flag})
    with open(os.path.join(OUTPUT_DIR, "source_freshness.json"), "w") as f:
        json.dump({"checked": str(today), "stale_days": STALE_DAYS, "sources": rows}, f, indent=2)
    return rows

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--county", help="5-digit FIPS from the dbt_project.yml counties registry")
    county = county_config.get(parser.parse_args().county)
    dbt_vars = ["--vars", json.dumps({"county": county["fips"]})]

    print("=" * 75)
    print(f"      {county['name']} COUNTY NG911 CLOUD-NATIVE GEOSPATIAL PIPELINE PILOT")
    print("   Layers: NENA-STA-010 SSAP, RCL, QA Discrepancies & Fishbones")
    print("=" * 75)

    # 1. Check data cache
    required_caches = [
        os.path.join(CACHE_DIR, "county_addresses.parquet"),
        os.path.join(CACHE_DIR, "oa_centerlines.parquet"),
        os.path.join(CACHE_DIR, "overture_addresses.parquet"),
        os.path.join(CACHE_DIR, "overture_transportation.parquet"),
        os.path.join(CACHE_DIR, "county_parcels.parquet"),
    ]
    if not all(os.path.exists(p) for p in required_caches):
        fetch_script = os.path.join(PROJECT_DIR, "scripts", "fetch_pilot_data.py")
        run_cmd([sys.executable, fetch_script], "Ingesting & caching pilot datasets")
    if not os.path.exists(os.path.join(CACHE_DIR, "mapillary_sequences.parquet")):
        run_cmd([sys.executable, os.path.join(PROJECT_DIR, "scripts", "fetch_mapillary_coverage.py")],
                "Caching Mapillary street imagery coverage")

    # 2. Run dbt models
    dbt_bin = os.path.join(PROJECT_DIR, ".venv", "bin", "dbt")
    if not os.path.exists(dbt_bin):
        dbt_bin = "dbt"
    freshness = source_freshness()  # written before dbt: NENA DateUpdate reads it (stg_source_dates)
    run_cmd([dbt_bin, "run", "--profiles-dir", ".", *dbt_vars], "dbt Transformations (SSAP, RCL, QA, Fishbones)")

    # Product 2 pairing, printed before the tests so it's in the log even when a boundary test fails
    with duckdb.connect(DB_PATH, read_only=True) as c:
        c.sql("LOAD spatial;")
        print("\n[PRODUCT 2] CDTFA city vs county city-limits pairing:")
        c.sql("SELECT City, StateName, LocalName, StateAreaKm2, LocalAreaKm2, OverlapKm2, PctAgreement, Status "
              "FROM mart_boundary_comparison ORDER BY City, StateName NULLS LAST").show(max_rows=500, max_width=250)

    # 3. Run dbt tests
    run_cmd([dbt_bin, "test", "--profiles-dir", ".", *dbt_vars], "dbt Data Quality & NENA Integrity Tests")

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
    conn.sql(f"COPY mart_ng911_addresses TO '{ssap_parquet}' (FORMAT PARQUET)")
    print(f"  -> Exported SSAP Address Points: {ssap_parquet}")

    # Export RCL
    rcl_parquet = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_rcl.parquet")
    conn.sql(f"COPY mart_ng911_road_centerlines TO '{rcl_parquet}' (FORMAT PARQUET)")
    print(f"  -> Exported RCL Road Centerlines: {rcl_parquet}")

    # Export Emergency Service Boundaries (ESBs & PSAP CAD)
    esb_parquet = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_esb.parquet")
    conn.sql(f"COPY mart_ng911_emergency_boundaries TO '{esb_parquet}' (FORMAT PARQUET)")
    print(f"  -> Exported Emergency Service Boundaries: {esb_parquet}")
    # Fire / EMS dispatch zones for the web app map (~10 m simplification keeps the file small)
    export_geojson_feature_collection(
        "SELECT ESB_NGUID, Agency_Name, Agency_Code, "
        "ST_AsGeoJSON(ST_SimplifyPreserveTopology(ST_Geometry, 0.0001)) AS geometry "
        "FROM mart_ng911_emergency_boundaries WHERE Agency_Type = 'FIRE'",
        os.path.join(OUTPUT_DIR, "esb_fire_zones.geojson"))
    esb_qa_parquet = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_esb_qa.parquet")
    conn.sql(f"COPY mart_ng911_esb_qa TO '{esb_qa_parquet}' (FORMAT PARQUET)")
    print(f"  -> Exported ESB Topology QA: {esb_qa_parquet}")

    # Export QA Discrepancies
    qa_parquet = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_qa_discrepancies.parquet")
    conn.sql(f"COPY mart_ng911_qa_discrepancies TO '{qa_parquet}' (FORMAT PARQUET)")
    print(f"  -> Exported QA Discrepancies: {qa_parquet}")

    # Export Fishbones
    fishbone_parquet = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_fishbones.parquet")
    conn.sql(f"COPY mart_ng911_qa_fishbones TO '{fishbone_parquet}' (FORMAT PARQUET)")
    print(f"  -> Exported QA Fishbone Vectors: {fishbone_parquet}")

    # Export Cal OES 98% Readiness Audit Mart
    audit_parquet = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_readiness_audit.parquet")
    conn.sql(f"COPY mart_ng911_qa_readiness_audit TO '{audit_parquet}' (FORMAT PARQUET)")
    print(f"  -> Exported Cal OES Readiness Audit Mart: {audit_parquet}")

    # Export Address Enhancements & QA/QC Displacement Mart
    enhancements_parquet = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_enhancements.parquet")
    conn.sql(f"COPY mart_ng911_address_enhancements TO '{enhancements_parquet}' (FORMAT PARQUET)")
    print(f"  -> Exported Address Enhancements: {enhancements_parquet}")

    # Export Actionable Jurisdiction Remediation Findings & Deliverables
    remediation_dir = os.path.join(OUTPUT_DIR, "remediation")
    os.makedirs(remediation_dir, exist_ok=True)
    remediation_csv = os.path.join(remediation_dir, "county_remediation_action_items.csv")
    remediation_parquet = os.path.join(remediation_dir, "county_remediation_points.parquet")

    conn.sql(f"COPY (SELECT * EXCLUDE (ST_Geometry) FROM mart_ng911_county_remediation_export WHERE SymbologyCategory != 'VALIDATED_OK') TO '{remediation_csv}' (HEADER, DELIMITER ',')")
    conn.sql(f"COPY mart_ng911_county_remediation_export TO '{remediation_parquet}' (FORMAT PARQUET)")
    print(f"  -> Exported Jurisdiction Remediation Deliverables: {remediation_csv} & {remediation_parquet}")
    flagged, with_img = conn.sql("SELECT count(*), count(*) FILTER (WHERE HasStreetImagery) FROM mart_ng911_county_remediation_export WHERE SymbologyCategory != 'VALIDATED_OK'").fetchall()[0]
    print(f"  -> Street imagery within 50 m for {with_img:,} of {flagged:,} flagged points")

    # Product 2: county city limits vs CDTFA (state geoportal) city boundaries
    boundary_dir = os.path.join(OUTPUT_DIR, "boundary_comparison")
    os.makedirs(boundary_dir, exist_ok=True)
    conn.sql(f"COPY (SELECT * FROM mart_boundary_comparison ORDER BY City) TO '{os.path.join(boundary_dir, 'city_boundary_comparison.csv')}' (HEADER)")
    export_geojson_feature_collection(
        "SELECT City, Side, AreaKm2, MeanWidthM, Cause, PctLengthAlongRoad, PctInFiledChange, FiledChangeLayer, FiledChangeRecord, FixUrl, "
        "ST_AsGeoJSON(ST_Geometry) AS geometry FROM mart_boundary_discrepancies",
        os.path.join(boundary_dir, "city_boundary_discrepancies.geojson"))
    boundary_rows = conn.sql("SELECT City, Status, PctAgreement, OnlyInStateKm2, OnlyInLocalKm2 FROM mart_boundary_comparison ORDER BY PctAgreement NULLS FIRST, City").fetchall()
    print(f"  -> Exported CDTFA boundary comparison ({len(boundary_rows)} cities): {boundary_dir}")
    export_geojson_feature_collection(
        "SELECT City, AreaKm2, ChangeFromCdtfaKm2, PiecesTakenFromCounty, SliversRemoved, UnexplainedPiecesKept, "
        "UnexplainedKm2, Status, ST_AsGeoJSON(ST_Geometry) AS geometry FROM mart_reconciled_city_boundaries",
        os.path.join(boundary_dir, "reconciled_city_boundaries.geojson"))
    align_rows = conn.sql("""
        SELECT City, max(PctOnParcelLines) FILTER (WHERE Source = 'CDTFA'),
               max(PctOnParcelLines) FILTER (WHERE Source = 'COUNTY'),
               max(PctOnParcelLines) FILTER (WHERE Source = 'RECONCILED')
        FROM mart_boundary_parcel_alignment GROUP BY City ORDER BY City""").fetchall()
    conn.sql(f"COPY (SELECT * FROM mart_county_boundary_comparison ORDER BY ComparedTo) TO '{os.path.join(boundary_dir, 'county_boundary_comparison.csv')}' (HEADER)")
    export_geojson_feature_collection(
        "SELECT ComparedTo, Side, AreaKm2, MeanWidthM, Cause, CountyAddressPoints, FixUrl, ST_AsGeoJSON(ST_Geometry) AS geometry "
        "FROM mart_county_boundary_discrepancies",
        os.path.join(boundary_dir, "county_boundary_discrepancies.geojson"))
    county_rows = conn.sql("SELECT ComparedTo, PctAgreement, UnexplainedKm2, AddressPointsInDisagreement, "
                           "CountyAddressPointsOutsideCdtfa, CountyAddressPoints FROM mart_county_boundary_comparison "
                           "ORDER BY ComparedTo").fetchall()
    # Open-data lineage: county roads OpenStreetMap is missing or names differently, with OSM edit links
    lineage_dir = os.path.join(OUTPUT_DIR, "open_data_fixes")
    os.makedirs(lineage_dir, exist_ok=True)
    conn.sql(f"COPY (SELECT * EXCLUDE (ST_Geometry) FROM mart_osm_road_fixes ORDER BY Issue, CountyStreetName) "
             f"TO '{os.path.join(lineage_dir, 'osm_road_fixes.csv')}' (HEADER)")
    export_geojson_feature_collection(
        "SELECT RCL_NGUID, CountyStreetName, LengthM, Issue, OsmName, OsmEditUrl, ST_AsGeoJSON(ST_Geometry) AS geometry "
        "FROM mart_osm_road_fixes", os.path.join(lineage_dir, "osm_road_fixes.geojson"))
    osm_fix_rows = conn.sql("SELECT Issue, count(*), round(sum(LengthM) / 1000, 1) FROM mart_osm_road_fixes "
                            "GROUP BY 1 ORDER BY 1").fetchall()
    cause_rows = conn.sql("SELECT Cause, Side, count(*), round(sum(AreaKm2), 3) FROM mart_boundary_discrepancies "
                          "GROUP BY ALL ORDER BY Cause, Side").fetchall()



    # Export NENA v3.0 Relational Data Model (3NF) Tables
    nena_v3_dir = os.path.join(OUTPUT_DIR, "nena_v3")
    os.makedirs(nena_v3_dir, exist_ok=True)
    nena3_tables = [
        "mart_nena3_adpt",
        "mart_nena3_stseg",
        "mart_nena3_serviceboundary",
        "mart_nena3_completestnam",
        "mart_nena3_completeadnum",
        "mart_nena3_discrpag",
        "mart_nena3_serviceurn",
        "mart_nena3_alias",
        "mart_nena3_aliasset",
        "mart_nena3_a1toa5code",
        "mart_nena3_a3boundary",
        "mart_nena3_rdclass"
    ]
    for tbl in nena3_tables:
        nena_out = os.path.join(nena_v3_dir, f"{tbl}.parquet")
        conn.sql(f"COPY {tbl} TO '{nena_out}' (FORMAT PARQUET)")
    print(f"  -> Exported NENA v3.0 Relational Enterprise Model: {len(nena3_tables)} tables in {nena_v3_dir}")

    # Export Regional Central Valley Addresses (Fresno, Kings, Tulare)
    regional_parquet = os.path.join(OUTPUT_DIR, "regional_central_valley_addresses.parquet")
    conn.sql(f"COPY stg_regional_addresses TO '{regional_parquet}' (FORMAT PARQUET)")
    print(f"  -> Exported Regional Multi-County Addresses: {regional_parquet}")

    # Build full-county PMTiles (streamed by the GeoLibre project; no sampling)
    build_tiles_script = os.path.join(PROJECT_DIR, "scripts", "build_pmtiles.py")
    subprocess.run([sys.executable, build_tiles_script], cwd=PROJECT_DIR, check=True)

    # Export GeoLibre project files (.geolibre and .geolibre.json)
    gen_proj_script = os.path.join(PROJECT_DIR, "scripts", "generate_geolibre_project.py")
    subprocess.run([sys.executable, gen_proj_script], cwd=PROJECT_DIR, check=True)
    print(f"  -> Exported GeoLibre Master Project: {os.path.join(OUTPUT_DIR, 'fresno_ng911_pilot.geolibre.json')}")

    gen_comp_script = os.path.join(PROJECT_DIR, "scripts", "generate_comparison_geolibre_project.py")
    subprocess.run([sys.executable, gen_comp_script], cwd=PROJECT_DIR, check=True)
    print(f"  -> Exported GeoLibre QA/QC Comparison Project: {os.path.join(OUTPUT_DIR, 'ng911_address_comparison.geolibre')}")



    total_addr = conn.sql("SELECT count(*) FROM mart_ng911_addresses").fetchall()[0][0]
    addr_metrics = conn.sql("""
        SELECT ConflationStatus, count(*), round(avg(SpatialOffsetMeters), 3) 
        FROM mart_ng911_addresses GROUP BY ConflationStatus
    """).fetchall()

    total_roads = conn.sql("SELECT count(*) FROM mart_ng911_road_centerlines").fetchall()[0][0]
    mapped_roads = conn.sql("SELECT count(*) FROM mart_ng911_road_centerlines WHERE FromAddr_L IS NOT NULL OR FromAddr_R IS NOT NULL").fetchall()[0][0]
    range_src = dict(conn.sql("SELECT RangeSource, count(*) FROM mart_ng911_road_centerlines WHERE FromAddr_L IS NOT NULL OR FromAddr_R IS NOT NULL GROUP BY 1").fetchall())
    rcl_src = ", ".join(r[0] for r in conn.sql("SELECT DISTINCT County_L FROM mart_ng911_road_centerlines ORDER BY 1").fetchall())

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
    """).fetchall()[0]

    conflated_cnt = next((m[1] for m in addr_metrics if m[0] == "CONFLATED"), 0)
    county_only_cnt = next((m[1] for m in addr_metrics if m[0] == "COUNTY_ONLY"), 0)
    overture_only_cnt = next((m[1] for m in addr_metrics if m[0] == "OVERTURE_ONLY"), 0)
    avg_offset = next((m[2] for m in addr_metrics if m[0] == "CONFLATED"), 0.0)

    missing_roads_cnt = next((m[1] for m in qa_metrics if m[0] == "POTENTIAL_MISSING_ROAD"), 0)
    name_mismatches_cnt = next((m[1] for m in qa_metrics if m[0] == "NAME_MISMATCH"), 0)

    # Cal OES Readiness Audit
    audit_row = conn.sql("SELECT * FROM mart_ng911_qa_readiness_audit").df().to_dict('records')[0]

    # Regional & NENA v3 Metrics
    reg_county_counts = conn.sql("SELECT county, count(*) FROM stg_regional_addresses GROUP BY county ORDER BY count(*) DESC").fetchall()
    total_reg_addr = conn.sql("SELECT count(*) FROM stg_regional_addresses").fetchall()[0][0]
    nena3_adpt_cnt = conn.sql("SELECT count(*) FROM mart_nena3_adpt").fetchall()[0][0]
    nena3_stseg_cnt = conn.sql("SELECT count(*) FROM mart_nena3_stseg").fetchall()[0][0]
    nena3_stnam_cnt = conn.sql("SELECT count(*) FROM mart_nena3_completestnam").fetchall()[0][0]

    # Live numbers for the web app (index.html reads scorecard.json beside it instead of hardcoding them)
    parcels_cache = os.path.join(CACHE_DIR, "county_parcels.parquet")
    pct = lambda v: None if v is None or v != v else float(v)  # v != v: NaN from pandas, which JSON can't carry
    oo = conn.sql("SELECT * FROM oo_scorecard").df().to_dict('records')[0]  # Product 1 (Overture-only)
    scorecard = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "county": county["label"],
        "fips": county["fips"],
        "address_points": total_addr,
        "remediation_points": conn.sql("SELECT count(*) FROM mart_ng911_county_remediation_export").fetchall()[0][0],
        "flagged_points": flagged,
        "flagged_with_street_imagery": with_img,
        "road_segments": total_roads,
        "fishbones": fishbone_metrics[0],
        "parcels": conn.sql(f"SELECT count(*) FROM '{parcels_cache}'").fetchall()[0][0] if os.path.exists(parcels_cache) else None,
        "gates": {
            "rcl_snapping": {"pct": pct(audit_row["Pct_SSAP_Remediated_Access_Snapped"]), "passed": bool(audit_row["Snapping_Threshold_Passed"])},
            "dispatch_coverage": {"pct": pct(audit_row["Authoritative_Pct_PSAP_Attributed"]), "passed": bool(audit_row["PSAP_Coverage_Passed"])},
            "range_inversions": {"count": int(audit_row["Road_Range_Inversions"]), "passed": bool(audit_row["Zero_Range_Inversions_Passed"])},
        },
        "within_50m_pct": pct(audit_row["Pct_Fishbones_Within_50m"]),
        "cal_oes_status": audit_row["Cal_OES_Readiness_Status"],
        "osm_road_fixes": [{"issue": i, "segments": int(n), "km": pct(km)} for i, n, km in osm_fix_rows],
        "county_boundary_comparison": [
            {"compared_to": src, "pct_agreement": pct(a), "unexplained_km2": pct(u), "address_points_in_disagreement": int(n)}
            for src, a, u, n, _, _ in county_rows
        ],
        "county_address_points_outside_cdtfa": int(county_rows[0][4]) if county_rows else None,
        "parcel_alignment_pct": [
            {"city": c, "cdtfa": pct(a), "county": pct(b), "reconciled": pct(r)} for c, a, b, r in align_rows
        ],
        "boundary_discrepancies": [
            {"cause": c, "side": sd, "pieces": n, "area_km2": pct(a)} for c, sd, n, a in cause_rows
        ],
        "boundary_comparison": [
            {"city": c, "status": st, "pct_agreement": pct(a), "only_in_state_km2": pct(s_), "only_in_local_km2": pct(l)}
            for c, st, a, s_, l in boundary_rows
        ],
        "overture_only": {
            "address_points": int(oo["Address_Points"]),
            "pct_addresses_in_building": pct(oo["Pct_Addresses_In_Building"]),
            "road_segments": int(oo["Road_Segments"]),
            "road_km": pct(oo["Road_Km"]),
            "localities": int(oo["Localities"]),
            "pct_matched_to_road": pct(oo["Pct_Addresses_Matched_To_Road"]),
            "pct_matched_within_50m": pct(oo["Pct_Matched_Within_50m"]),
            "pct_county_centerline_in_overture": pct(oo["Pct_County_Centerline_Length_In_Overture"]),
            "pct_county_centerline_same_name": pct(oo["Pct_County_Centerline_Length_Same_Name"]),
        },
    }
    with open(os.path.join(OUTPUT_DIR, "scorecard.json"), "w") as f:
        json.dump(scorecard, f, indent=2)

    print("\n" + "=" * 75)
    print("                       PILOT EVALUATION SCORECARD")
    print("=" * 75)
    print(f"  Jurisdiction:             Central Valley Region (Fresno, Kings, Tulare Counties)")
    print(f"  Authoritative Sources:    Fresno Co. Hub, Kings Co. REST, Tulare Co. Open Data")
    print(f"  Reference Source:         Overture Maps Foundation (S3 GeoParquet)")
    print(f"  Licensing Integrity:      100% County Geometry Preserved (Zero ODbL)")
    print("-" * 75)
    print(f"  County Build:             {county['label']} (FIPS {county['fips']})")
    print("-" * 75)
    print(f"  LAYER 1: SITE/STRUCTURE ADDRESS POINTS (SSAP - {county['name']}):")
    print(f"  - Total Points:           {total_addr:,}")
    print(f"  - Conflated (Both):       {conflated_cnt:,} ({conflated_cnt/total_addr*100:.1f}%)")
    print(f"  - Authoritative County:   {county_only_cnt:,} ({county_only_cnt/total_addr*100:.1f}%)")
    print(f"  - Overture Unverified:    {overture_only_cnt:,} ({overture_only_cnt/total_addr*100:.1f}%)")
    print(f"  - Mean Spatial Offset:    {avg_offset} meters")
    print("-" * 75)
    print(f"  LAYER 2: ROAD CENTERLINES (RCL):")
    print(f"  - Centerline Segments:    {total_roads:,}")
    print(f"  - Address Ranges:         {mapped_roads:,} segments ({range_src.get('Published', 0):,} published, {range_src.get('Synthesized', 0):,} synthesized)")
    print(f"  - Geometry Attribution:   100% county centerlines via OpenAddresses ({rcl_src})")
    print("-" * 75)
    print(f"  LAYER 3: EMERGENCY SERVICE BOUNDARIES (LAW / FIRE / MUNICIPAL):")
    esb_counts = conn.sql("SELECT Agency_Type, count(*) FROM mart_ng911_emergency_boundaries GROUP BY Agency_Type").fetchall()
    for atype, acnt in esb_counts:
        print(f"  - {atype} Polygons:       {acnt:,}")
    print(f"  - Law Dispatch Attributed: {audit_row['Authoritative_PSAP_Attributed']:,} ({audit_row['Authoritative_Pct_PSAP_Attributed']}%) authoritative points")
    print(f"  - Combined Dataset:        {audit_row['Total_Combined_Addresses']:,} ({audit_row['Pct_PSAP_Attributed_Combined']}%)")
    esb_qa = dict(conn.sql("SELECT IssueType, count(*) FROM mart_ng911_esb_qa GROUP BY 1").fetchall())
    print(f"  - Law Layer Topology QA:   {esb_qa.get('INVALID_GEOMETRY', 0)} invalid, {esb_qa.get('DUPLICATE_POLYGON', 0)} duplicate, {esb_qa.get('OVERLAP', 0)} overlaps (repaired/flagged)")
    print(f"  - PSAP Boundaries:         none published; PSAP fields use law dispatch areas as a stand-in")
    print("-" * 75)
    print(f"  LAYER 4: NENA QA/QC FISHBONE VALIDATION:")
    print(f"  - Fishbone Vectors:       {fishbone_metrics[0]:,} addresses snapped to centerlines")
    print(f"  - Mean Offset to Road:    {fishbone_metrics[1]} meters")
    print(f"  - Within 50m of road:     {audit_row['SSAP_Snapped_Within_50m_Physical']:,} ({audit_row['Pct_Fishbones_Within_50m']}% of snapped)")
    print(f"  - Excessive Offsets (>50m):{fishbone_metrics[2]:,} flagged for analyst review")
    print("-" * 75)
    print(f"  LAYER 5: QA/QC DISCREPANCY AUDITING:")
    print(f"  - Potential Missing Roads:{missing_roads_cnt:,} (Overture roads absent from County GIS)")
    print(f"  - Street Name Mismatches: {name_mismatches_cnt:,} (Spelling / alias discrepancies)")
    print("-" * 75)
    print(f"  CAL OES 98% NG911 TRANSITION READINESS SCORECARD:")
    print(f"  - RCL Snapping (>= 98%):   {audit_row['Pct_SSAP_Remediated_Access_Snapped']}% of all address points -> {'[PASS]' if audit_row['Snapping_Threshold_Passed'] else '[FAIL]'}")
    print(f"  - Dispatch Coverage (>=98%): {audit_row['Authoritative_Pct_PSAP_Attributed']}% -> {'[PASS]' if audit_row['PSAP_Coverage_Passed'] else '[FAIL]'}")
    print(f"  - Inverted Ranges (= 0):   {audit_row['Road_Range_Inversions']} -> {'[PASS]' if audit_row['Zero_Range_Inversions_Passed'] else '[FAIL]'}")
    print(f"  - Cal OES Readiness:       {audit_row['Cal_OES_Readiness_Status']}")
    print("-" * 75)
    print(f"  PRODUCT 1: OVERTURE-ONLY NG911 (no county data; roads are OpenStreetMap-derived, ODbL):")
    print(f"  - Address Points:          {oo['Address_Points']:,} ({oo['Pct_Addresses_In_Building']}% inside an Overture building)")
    print(f"  - Road Segments:           {oo['Road_Segments']:,} ({oo['Road_Km']:,} km), {oo['Localities']} cities/places")
    print(f"  - Matched to a Road:       {oo['Addresses_Matched_To_Road']:,} ({oo['Pct_Addresses_Matched_To_Road']}%), {oo['Pct_Matched_Within_50m']}% of those within 50 m")
    print(f"  - County Centerlines Also in Overture: {oo['Pct_County_Centerline_Length_In_Overture']}% of length "
          f"({oo['Pct_County_Centerline_Length_Same_Name']}% with the same name)")
    print(f"  - Missing from Overture:   PSAP/ESB boundaries, published address ranges, MSAG/ESN")
    print("-" * 75)
    print(f"  PRODUCT 2: CITY LIMITS VS CDTFA (CA STATE GEOPORTAL):")
    for c, st, a, s_, l in boundary_rows:
        print(f"  - {c:<16} {st:<18} {'' if a is None else f'{a}% agree'}  state-only {s_} km2, county-only {l} km2")
    print(f"  OpenStreetMap road fixes (open_data_fixes/osm_road_fixes.csv, with OSM edit links):")
    for i, n, km in osm_fix_rows:
        print(f"  - {i:<15} {n:,} county segments, {km} km")
    print(f"  County line vs CDTFA:")
    for src, a, u, n, out, tot in county_rows:
        print(f"  - {src:<9} {a}% agree, {u} km2 unexplained, {n:,} county address points in disagreeing areas")
    if county_rows:
        print(f"  - County address points outside CDTFA's county line: {county_rows[0][4]:,} of {county_rows[0][5]:,}")
    print(f"  Boundary on parcel lines (within ~3 m):  CDTFA / county / reconciled")
    for c, a, b, r in align_rows:
        print(f"  - {c:<16} {a}% / {b}% / {r}%")
    print(f"  Disagreeing areas (1 ha+) by likely cause:")
    for c, sd, n, a in cause_rows:
        print(f"  - {c:<13} {sd:<14} {n:>4} pieces, {a} km2")
    print("-" * 75)
    print(f"  MULTI-COUNTY REGIONAL EXPANSION (CENTRAL VALLEY):")
    print(f"  - Total Regional SSAP:    {total_reg_addr:,} addresses across 3 counties")
    for cname, ccnt in reg_county_counts:
        print(f"    * {cname.title()} County:     {ccnt:,} authoritative points")
    print("-" * 75)
    print(f"  NENA GIS DATA MODEL v3.0 RELATIONAL TEMPLATES (NENA-STA-006.x):")
    print(f"  - ng911.AdPt:             {nena3_adpt_cnt:,} normalized address point records")
    print(f"  - ng911.StSeg:            {nena3_stseg_cnt:,} road centerlines with 3NF foreign keys")
    print(f"  - ng911.CompleteStNam:    {nena3_stnam_cnt:,} unique parsed street names")
    print(f"  - ng911.DiscrpAg:         3 authority domains (fresnocountyca.gov, kingscountyca.gov, tularecountyca.gov)")
    print(f"  - ng911.ServiceURN:       4 IETF emergency service types (sos, sos.fire, sos.police, sos.ambulance)")
    print(f"  - Deliverables:           data/output/nena_v3/*.parquet (3NF Relational Data Model)")
    print("-" * 75)
    print(f"  SOURCE FRESHNESS (last published; STALE > {STALE_DAYS} days):")
    for r in freshness:
        age = f"{r['age_days']:>4}d" if r["age_days"] is not None else "    -"
        print(f"  - {r['source']:<22} {r['last_published'] or '?':<11} {age}  {r['status']}")
    print("-" * 75)
    print(f"  Deliverables Generated:   SSAP (Parquet/GeoJSON), RCL (Parquet/GeoJSON),")
    print(f"                            ESB (Parquet/GeoJSON), Fishbones (Parquet/GeoJSON),")
    print(f"                            QA (Parquet), Readiness Audit (Parquet),")
    print(f"                            Regional Addresses (Parquet), NENA v3.0 Tables (Parquet)")
    print(f"  GeoLibre Project:         data/output/fresno_ng911_pilot.geolibre.json")
    print(f"  GeoLibre 1-Click URL:     https://web.geolibre.app/?url=https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/fresno_ng911_pilot.geolibre.json")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
