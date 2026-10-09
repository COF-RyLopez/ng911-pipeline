#!/usr/bin/env python3
"""
scripts/build_pmtiles.py

Builds full-county PMTiles vector tile archives for the GeoLibre 1-click project.

Why: inlining GeoJSON into the .geolibre.json project caps out around ~40k features
before the file blows past GitHub's 50/100 MB limits. PMTiles archives are read by
HTTP range requests, so GeoLibre only downloads the tiles in view. This lets the
1-click map show 100% of address points, centerlines and fishbones.

Output (data/output/tiles/):
  - fresno_ssap.pmtiles       all SSAP address points (County, Conflated, Overture-only)
  - fresno_rcl.pmtiles        all road centerlines
  - fresno_fishbones.pmtiles  all QA/QC fishbone vectors
  - fresno_esb.pmtiles        all emergency service boundaries

Requires: tippecanoe (brew install tippecanoe)
"""

import os
import shutil
import subprocess
import sys

import duckdb

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "data", "output")
TILES_DIR = os.path.join(OUTPUT_DIR, "tiles")
TMP_DIR = os.path.join(PROJECT_DIR, "data", "cache", "tiles_tmp")

# layer name -> (parquet file, SELECT columns, tippecanoe args, optional geom_col)
LAYERS = {
    "ssap": (
        "mart_ng911_fresno_ssap.parquet",
        """SSAP_NGUID, ConflationStatus, Source, HNO, HNS, PRD, STN, STS, POD, Unit,
           Muni, CommunityName, PostCode, PSAP, ESB_Fire, LandmarkName,
           round(SpatialOffsetMeters, 2) AS SpatialOffsetMeters""",
        ["-Z9", "-z16", "--no-tile-size-limit"],
        "ST_Geometry"
    ),
    "rcl": (
        "mart_ng911_fresno_rcl.parquet",
        """RCL_NGUID, FullStreetName, FromAddr_L, ToAddr_L, FromAddr_R, ToAddr_R,
           Parity_L, Parity_R, RoadClass, SpeedLimit, OneWay""",
        ["-Z8", "-z16", "--no-line-simplification", "--no-tiny-polygon-reduction",
         "--no-tile-size-limit"],
        "ST_Geometry"
    ),
    "fishbones": (
        "mart_ng911_fresno_fishbones.parquet",
        """FishboneID, SSAP_NGUID, RCL_NGUID, HNO, STN,
           round(DistanceMeters, 1) AS DistanceMeters, IsExcessiveOffset, IsRangeViolation""",
        ["-Z10", "-z16", "--drop-densest-as-needed", "--extend-zooms-if-still-dropping"],
        "ST_Geometry"
    ),
    "esb": (
        "mart_ng911_fresno_esb.parquet",
        "ESB_NGUID, Agency_Type, Agency_Name, Agency_Code, ServiceNum, Area_Code",
        ["-Z6", "-z15", "--no-tiny-polygon-reduction", "--detect-shared-borders"],
        "ST_Geometry"
    ),
    "remediation": (
        "remediation/county_remediation_points.parquet",
        """SSAP_NGUID, CountyLocalID, HNO, STN, StandardizedAddress,
           round(SpatialOffsetMeters, 1) AS SpatialOffsetMeters,
           BuildingFootprintStatus, SymbologyCategory, DiscrepancyType, Severity,
           OvertureAddressGERS_ID, OvertureBuildingGERS_ID, RoadCenterlineNGUID,
           IsExcessiveOffset, IsRangeViolation, PSAP, ESB_Fire,
           MapillaryGroundTruthURL, RecommendedRemediationAction""",
        ["-Z9", "-z16", "--no-tile-size-limit"],
        "ST_Geometry"
    ),
    "buildings": (
        "../cache/overture_buildings.parquet",
        "building_id, height, num_floors, building_class",
        ["-Z13", "-z16", "--no-tile-size-limit"],
        "geom"
    ),
    "parcels": (
        "../cache/county_parcels.parquet",
        "parcel_id, apn, agency_code, roll_year",
        ["-Z12", "-z16", "--no-tile-size-limit"],
        "geom"
    ),
}


def main():
    if not shutil.which("tippecanoe"):
        print("[WARNING] tippecanoe not found in PATH. Skipping PMTiles vector tile build.")
        return

    os.makedirs(TILES_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    conn = duckdb.connect()
    conn.sql("INSTALL spatial; LOAD spatial;")

    selected = [sys.argv[1]] if len(sys.argv) > 1 and sys.argv[1] in LAYERS else list(LAYERS.keys())
    print(f"Building PMTiles for: {', '.join(selected)}")

    for name in selected:
        item = LAYERS[name]
        parquet = item[0]
        cols = item[1]
        tip_args = item[2]
        geom_col = item[3] if len(item) > 3 else "ST_Geometry"

        src = os.path.join(OUTPUT_DIR, parquet)
        if not os.path.exists(src):
            print(f"Skipping tile build for {name}: {src} missing.")
            continue

        seq = os.path.join(TMP_DIR, f"{name}.geojsonl")
        out = os.path.join(TILES_DIR, f"fresno_{name}.pmtiles")
        for p in (seq, out):
            if os.path.exists(p):
                os.remove(p)

        conn.sql(f"""
            COPY (SELECT {cols}, {geom_col} AS geom FROM '{src}' WHERE {geom_col} IS NOT NULL)
            TO '{seq}' WITH (FORMAT GDAL, DRIVER 'GeoJSONSeq', LAYER_CREATION_OPTIONS 'COORDINATE_PRECISION=6')
        """)
        n = conn.sql(f"SELECT count(*) FROM '{src}' WHERE {geom_col} IS NOT NULL").fetchone()[0]

        cmd = ["tippecanoe", "-q", "-f", "-o", out, "-l", name,
               "--attribution", "County of Fresno (authoritative); Overture Maps Foundation"] + tip_args + [seq]
        subprocess.run(cmd, check=True)
        os.remove(seq)
        print(f"  -> {out}  ({n:,} features, {os.path.getsize(out) / 1e6:.1f} MB)")

    shutil.rmtree(TMP_DIR, ignore_errors=True)



if __name__ == "__main__":
    main()
