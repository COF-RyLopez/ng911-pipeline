# NG911 Cloud-Native Geospatial Pipeline (Fresno County Pilot)

An end-to-end Python, DuckDB, and dbt pipeline designed to ingest municipal/county GIS endpoints (Fresno County ArcGIS Regional Address, Street, CAD/PSAP, and Fire District FeatureServers), conflate them with Overture Maps global GeoParquet data, and structure them natively into a NENA-STA-010-compliant Next Generation 911 (NG911) dataset with automated Cal OES 98% Transition Readiness Auditing.

---

## Architecture & Directory Structure

```text
ng911_pipeline/
├── dbt_project.yml          # dbt project configuration & pilot variables
├── profiles.yml             # Connection profiles (DuckDB target with spatial & httpfs)
├── macros/
│   └── geometry_helpers.sql # Custom macros for geometry conversions (WKB, points, spatial filters)
├── models/
│   ├── schema.yml           # Data tests & NENA compliance assertions (57 tests)
│   ├── staging/
│   │   ├── stg_county_addresses.sql       # Authoritative Fresno County ArcGIS addresses
│   │   ├── stg_county_streets.sql         # Authoritative Fresno County street centerlines
│   │   ├── stg_county_boundaries.sql      # Authoritative CAD/PSAP, Fire District & City Limits
│   │   ├── stg_overture_addresses.sql     # Bounded Overture GeoParquet address queries
│   │   ├── stg_overture_places.sql        # Authoritative Landmark & POI locations (Overture Places)
│   │   └── stg_overture_transportation.sql# Overture road segments (QA/QC reference)
│   ├── intermediate/
│   │   ├── int_address_conflation.sql     # 15m spatial buffer join & component normalization
│   │   └── int_address_landmarks.sql      # Proximity matching linking addresses to landmarks within 60m
│   └── marts/
│       ├── mart_ng911_addresses.sql       # NENA-STA-010 SSAP with automated ESB dispatch & landmark attribution
│       ├── mart_ng911_road_centerlines.sql# NENA-STA-010 RCL schema with synthesized address ranges
│       ├── mart_ng911_emergency_boundaries.sql # Unified NENA Emergency Service Boundaries (ESBs: PSAP, Fire, Muni)
│       ├── mart_ng911_qa_discrepancies.sql# Missing roads and street name mismatch audit
│       ├── mart_ng911_qa_fishbones.sql    # Perpendicular vector lines validating address-to-street distance & parity
│       └── mart_ng911_qa_readiness_audit.sql # Cal OES 98% NG911 Transition Readiness Audit scorecard
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
    └── output/              # Final GIS deliverables (Parquet, GeoJSON, and GeoLibre projects)
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

To execute the entire pilot end-to-end (ingest, dbt transformation, 57 data quality tests, and GIS exports):

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
- **Run Automated Data Quality & NENA Integrity Tests (57 Tests):**
  ```bash
  ./.venv/bin/dbt test --profiles-dir .
  ```

---

## Zero-Install GIS Viewing & Statewide Sharing via GeoLibre

To allow anyone—especially non-ESRI agencies and dispatch centers across California—to inspect the pilot results without installing desktop GIS software:

### Option 1: 1-Click Complete Map Project
Open the pre-styled, self-contained project (amber boundary polygons, green centerlines, blue address points with dispatch popups, red fishbones, and a 3-widget dashboard) directly in GeoLibre:
```text
https://web.geolibre.app/?url=https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/fresno_ng911_pilot.geolibre.json
```
*(Or drag and drop `data/output/fresno_ng911_pilot.geolibre` straight into [web.geolibre.app](https://web.geolibre.app/)).*

### Option 2: Additive Layer Streaming (No Workspace Reset)
In GeoLibre, open **Add Vector Layer**, paste any of the public GitHub endpoints below, and check **"Stream GeoParquet (no copy)"**:
- **NENA Emergency Service Boundaries (1.09 MB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/mart_ng911_fresno_esb.parquet`
- **NENA SSAP Address Points with Dispatch Routing (1.32 MB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/mart_ng911_fresno_ssap.parquet`
- **NENA Road Centerlines (420 KB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/mart_ng911_fresno_rcl.parquet`
- **QA/QC Fishbone Vectors (203 KB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/mart_ng911_fresno_fishbones.parquet`
- **QA Discrepancies (329 KB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/mart_ng911_fresno_qa_discrepancies.parquet`

*(Standard GeoJSON fallbacks are also available at `..._sample.geojson`).*

---

## Key Compliance & Architectural Highlights

1. **Complete NENA Core 4 Layers:**
   - **SSAP (Site/Structure Address Points):** Enriched with automated point-in-polygon PSAP CAD and Fire ESB routing, plus Overture landmark POI dispatch aliases (`LandmarkName`).
   - **RCL (Road Centerlines):** Synthesized address ranges (`FromAddr_L`, `ToAddr_L`, `FromAddr_R`, `ToAddr_R`) with speed limits and road classes.
   - **ESB (Emergency Service Boundaries):** Authoritative CAD/PSAP dispatch polygons, fire protection districts, and incorporated city limits.
   - **QA Fishbones:** Vector lines validating address snapping distances and parity against road centerlines.
2. **Cal OES 98% Transition Readiness Audit Mart (`mart_ng911_qa_readiness_audit`):**
   - Automatically checks $\ge 98\%$ RCL snapping compliance within 50m.
   - Audits $100\%$ PSAP boundary coverage.
   - Asserts zero address range inversions across all centerline segments.
3. **ODbL Licensing Isolation:** 100% of the geometry in the Road Centerlines mart belongs to Fresno County GIS (`REGIONAL_STREETS_VW`). Overture/OSM geometry is strictly isolated to read-only QA/QC comparison.
4. **NENA Standards Supported:**
   - `SSAP_NGUID`: `urn:emergency:uid:gis:SSAP:<id>:fresnocountyca.gov`
   - `RCL_NGUID`: `urn:emergency:uid:gis:RCL:<id>:fresnocountyca.gov`
   - `ESB_NGUID`: `urn:emergency:uid:gis:ESB:<type>:<id>:fresnocountyca.gov`
   - Mandatory `DisclID` and external federation `GERS_ID`.
