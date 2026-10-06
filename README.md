# NG911 Cloud-Native Geospatial Pipeline (Fresno County Pilot)

An end-to-end Python, DuckDB, and dbt pipeline designed to ingest municipal/county GIS endpoints (Fresno County ArcGIS Regional Address and Street FeatureServers), conflate them with Overture Maps global GeoParquet data, and structure them natively into a NENA-STA-010-compliant Next Generation 911 (NG911) Site/Structure Address Point (SSAP) and Road Centerline (RCL) dataset.

---

## Architecture & Directory Structure

```text
ng911_pipeline/
├── dbt_project.yml          # dbt project configuration & pilot variables
├── profiles.yml             # Connection profiles (DuckDB target with spatial & httpfs)
├── macros/
│   └── geometry_helpers.sql # Custom macros for geometry conversions (WKB, points, spatial filters)
├── models/
│   ├── schema.yml           # Data tests & NENA compliance assertions (37 tests)
│   ├── staging/
│   │   ├── stg_county_addresses.sql       # Authoritative Fresno County ArcGIS addresses
│   │   ├── stg_county_streets.sql         # Authoritative Fresno County street centerlines
│   │   ├── stg_overture_addresses.sql     # Bounded Overture GeoParquet address queries
│   │   └── stg_overture_transportation.sql# Overture road segments (QA/QC reference)
│   ├── intermediate/
│   │   └── int_address_conflation.sql     # 15m spatial buffer join & component normalization
│   └── marts/
│       ├── mart_ng911_addresses.sql       # NENA-STA-010 SSAP schema (Site/Structure Address Points)
│       ├── mart_ng911_road_centerlines.sql# NENA-STA-010 RCL schema with synthesized address ranges
│       ├── mart_ng911_qa_discrepancies.sql# Missing roads and street name mismatch audit
│       └── mart_ng911_qa_fishbones.sql    # Perpendicular vector lines validating address-to-street distance & parity
├── scripts/
│   ├── fetch_pilot_data.py   # Ingest and cache Fresno County & Overture pilot data
│   ├── run_pilot.py          # End-to-end execution, testing, and GIS export
│   └── serve_for_geolibre.py # CORS-enabled HTTP server for zero-install viewing in https://web.geolibre.app/
├── sources/
│   └── us/ca/
│       ├── fresno.json               # Fresno County ArcGIS source definition
│       └── surrounding_counties.json # Madera, Kings, and Tulare configurations
└── data/
    ├── cache/               # Cached parquet extracts for rapid development
    └── output/              # Final GIS deliverables (Parquet and GeoJSON)
```

---

## Setup & Prerequisites

1. Ensure Python 3.12+ and virtual environment are configured:
   ```bash
   uv venv --python 3.12
   uv pip install --python .venv dbt-duckdb pandas
   ```

---

## Running the Pilot Pipeline

To execute the entire pilot end-to-end (ingest, dbt transformation, 37 data quality tests, and GIS exports):

```bash
./.venv/bin/python scripts/run_pilot.py
```

### Running Individual Pipeline Stages

- **Fetch / Refresh Cache:**
  ```bash
  ./.venv/bin/python scripts/fetch_pilot_data.py
  ```
- **Run dbt Transformations:**
  ```bash
  ./.venv/bin/dbt run --profiles-dir .
  ```
- **Run Automated Data Quality & NENA Integrity Tests (37 Tests):**
  ```bash
  ./.venv/bin/dbt test --profiles-dir .
  ```

---

## Zero-Install GIS Viewing & Statewide Sharing via GeoLibre

To allow anyone—especially non-ESRI agencies across California—to inspect the pilot results without installing desktop GIS software:

### Option 1: 1-Click Complete Map Project
Open the pre-styled, self-contained project (red fishbones, blue points, green centerlines, popups, and dashboard charts) directly in GeoLibre:
```text
https://web.geolibre.app/?url=https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/fresno_ng911_pilot.geolibre.json
```
*(Or drag and drop `data/output/fresno_ng911_pilot.geolibre` straight into [web.geolibre.app](https://web.geolibre.app/)).*

### Option 2: Additive Layer Streaming (No Workspace Reset)
In GeoLibre, open **Add Vector Layer**, paste any of the public GitHub endpoints below, and check **"Stream GeoParquet (no copy)"**:
- **QA/QC Fishbone Vectors (198 KB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/mart_ng911_fresno_fishbones.parquet`
- **NENA SSAP Address Points (1.3 MB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/mart_ng911_fresno_ssap.parquet`
- **NENA Road Centerlines (411 KB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/mart_ng911_fresno_rcl.parquet`
- **QA Discrepancies (322 KB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/mart_ng911_fresno_qa_discrepancies.parquet`

*(Standard GeoJSON fallbacks are also available at `..._sample.geojson`).*

---

## Key Compliance & Architectural Highlights

1. **ODbL Licensing Isolation:** 100% of the geometry in the Road Centerlines mart belongs to Fresno County GIS (`REGIONAL_STREETS_VW`). Overture/OSM geometry is strictly isolated to read-only QA/QC comparison.
2. **Automated Address Range Synthesis:** Centerlines are enriched with synthesized `FromAddr_L`, `ToAddr_L`, `FromAddr_R`, and `ToAddr_R` ranges calculated by projecting authoritative address points onto street segments.
3. **NENA-STA-010 Fishbone Validation:** Vector connection lines calculate distance to road and flag points sitting $>50\text{m}$ away or violating street address ranges.
4. **NENA Standards Supported:**
   - `SSAP_NGUID`: `urn:emergency:uid:gis:SSAP:<id>:fresnocountyca.gov`
   - `RCL_NGUID`: `urn:emergency:uid:gis:RCL:<id>:fresnocountyca.gov`
   - Mandatory `DisclID` and external federation `GERS_ID`.
