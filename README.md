# NG911 Cloud-Native Geospatial Pipeline (Central Valley Regional Pilot)

An end-to-end Python, DuckDB, and dbt pipeline designed to ingest municipal and county GIS endpoints across California's Central Valley (**Fresno**, **Kings**, and **Tulare** Counties), conflate them with Overture Maps global GeoParquet data, and structure them natively into a **Dual-Model NG9-1-1 Architecture**:
1. **Model A — NENA v3.0 Relational Data Model (`NENA-STA-006.3-2026`)**: Fully normalized 3NF relational schema matching the official [NENA GIS Data Model v3.0](https://github.com/NENA911/NG911GISDataModel/blob/main/relational_templates/schema/v3.0/README.md).
2. **Model B — NENA-STA-010 GIS Exchange Model**: Optimized flat GeoParquet layers for zero-install streaming in [GeoLibre](https://web.geolibre.app/), QGIS, CAD/PSAP integration, and automated **Cal OES 98% Transition Readiness Auditing**.

---

## Dual-Model Architecture & Directory Structure

```text
ng911_pipeline/
├── dbt_project.yml          # dbt project configuration & pilot variables
├── profiles.yml             # Connection profiles (DuckDB target with spatial & httpfs)
├── macros/
│   └── geometry_helpers.sql # Custom macros for geometry conversions (WKB, points, spatial filters)
├── models/
│   ├── schema.yml           # Data tests & NENA compliance assertions (83 tests)
│   ├── staging/
│   │   ├── stg_county_addresses.sql       # Authoritative Fresno County ArcGIS addresses (238k points)
│   │   ├── stg_county_streets.sql         # Authoritative Fresno County street centerlines (53k segments)
│   │   ├── stg_county_boundaries.sql      # Authoritative CAD/PSAP, Fire District & City Limits
│   │   ├── stg_regional_addresses.sql     # Unified Central Valley addresses (Fresno, Kings, Tulare: 386k points)
│   │   ├── stg_overture_addresses.sql     # Bounded Overture GeoParquet address queries
│   │   ├── stg_overture_places.sql        # Authoritative Landmark & POI locations (Overture Places)
│   │   └── stg_overture_transportation.sql# Overture road segments (QA/QC reference)
│   ├── intermediate/
│   │   ├── int_address_conflation.sql     # 15m spatial buffer join & component normalization
│   │   └── int_address_landmarks.sql      # Proximity matching linking addresses to landmarks within 60m
│   └── marts/
│       ├── nena_v3_relational/            # === MODEL A: OFFICIAL NENA v3.0 RELATIONAL MODEL ===
│       │   ├── mart_nena3_adpt.sql            # ng911.AdPt (Site/Structure Address Point)
│       │   ├── mart_nena3_stseg.sql           # ng911.StSeg (Road Centerline Segment)
│       │   ├── mart_nena3_serviceboundary.sql # ng911.ServiceBoundary (ESB Polygons with ServiceURN FK)
│       │   ├── mart_nena3_completestnam.sql   # ng911.CompleteStNam (Normalized Street Names table)
│       │   ├── mart_nena3_completeadnum.sql   # ng911.CompleteAdNum (Normalized Address Numbers table)
│       │   ├── mart_nena3_discrpag.sql        # ng911.DiscrpAg (Discrepancy Agency authoritative domains)
│       │   └── mart_nena3_serviceurn.sql      # ng911.ServiceURN (IETF RFC 5031 Emergency Service Types)
│       └── ...                            # === MODEL B: NENA-STA-010 FLAT EXCHANGE MODEL ===
│           ├── mart_ng911_addresses.sql       # SSAP with automated ESB dispatch & landmark attribution
│           ├── mart_ng911_road_centerlines.sql# RCL schema with synthesized address ranges
│           ├── mart_ng911_emergency_boundaries.sql # Unified ESBs (PSAP, Fire, Muni)
│           ├── mart_ng911_qa_discrepancies.sql# Missing roads and street name mismatch audit
│           ├── mart_ng911_qa_fishbones.sql    # Perpendicular vector lines validating address snapping
│           └── mart_ng911_qa_readiness_audit.sql # Cal OES 98% NG911 Transition Readiness Audit scorecard
├── scripts/
│   ├── fetch_pilot_data.py   # Ingest and cache Fresno, Kings, and Tulare county GIS data
│   ├── run_pilot.py          # End-to-end execution, testing, and GIS export
│   └── serve_for_geolibre.py # CORS-enabled HTTP server for zero-install viewing in https://web.geolibre.app/
├── sources/
│   └── us/ca/
│       ├── fresno.json               # Fresno County ArcGIS source definition
│       └── surrounding_counties.json # Madera, Kings, and Tulare configurations
└── data/
    ├── cache/               # Cached parquet extracts for rapid development
    └── output/              # Final GIS deliverables (Parquet, GeoJSON, and GeoLibre projects)
        └── nena_v3/         # Exported NENA v3.0 Relational parquet tables
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

To execute the entire pilot end-to-end (ingest, dbt transformation, 83 data quality tests, and GIS exports):

```bash
./.venv/bin/python scripts/run_pilot.py
```

### Running Individual Pipeline Stages

- **Fetch / Refresh Cache (Fresno, Kings, Tulare):**
  ```bash
  ./.venv/bin/python scripts/fetch_pilot_data.py
  ```
- **Run dbt Transformations (All 23 Models):**
  ```bash
  ./.venv/bin/dbt run --profiles-dir .
  ```
- **Run Automated Data Quality & NENA Integrity Tests (83 Tests):**
  ```bash
  ./.venv/bin/dbt test --profiles-dir .
  ```

---

## Multi-County Regional Metrics (Central Valley)

| County | Authoritative Address Count | Ingestion Method | Status |
| :--- | :--- | :--- | :--- |
| **Fresno County** | **395,107** (466,751 total SSAP) | ArcGIS Hub `REGIONAL_ADDRESS_VW` (Active + Current + Pending) | Verified Authoritative |
| **Tulare County** | **170,483** | Open Data FeatureServer | Verified Authoritative |
| **Kings County** | **51,877** | Parallel REST Server | Verified Authoritative |
| **Total Central Valley** | **617,467 addresses** | High-Speed Stream Ingest | **100% Authoritative** |

---

## Official NENA v3.0 Relational Model (`NENA-STA-006.3-2026`)

Deliverables exported to `data/output/nena_v3/`:
- **`mart_nena3_adpt.parquet` (618,633 rows, 26.0 MB)**: Normalized 3NF address points linking foreign keys to `DiscrpAg_ID`, `CompleteStNam_ID`, and `CompleteAdNum_ID`.
- **`mart_nena3_stseg.parquet` (53,576 rows, 6.6 MB)**: Street centerline segments with 3NF foreign keys to `CompleteStNam_ID` and `DiscrpAg_ID`.
- **`mart_nena3_serviceboundary.parquet` (80 rows, 1.0 MB)**: MultiPolygon emergency service boundaries referencing `ServiceURN_ID` and `DiscrpAg_ID`.
- **`mart_nena3_completestnam.parquet` (12,708 rows)**: Normalized street components (`St_PreDir`, `St_Name`, `St_Typ`, `St_PosDir`).
- **`mart_nena3_completeadnum.parquet` (37,249 rows)**: Normalized address numbers (`Add_Number`, `AddNum_Suf`).
- **`mart_nena3_discrpag.parquet` (3 rows)**: Authority registry (`fresnocountyca.gov`, `kingscountyca.gov`, `tularecountyca.gov`).
- **`mart_nena3_serviceurn.parquet` (4 rows)**: RFC 5031 service identifiers (`sos`, `sos.fire`, `sos.police`, `sos.ambulance`).

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
- **NENA Emergency Service Boundaries (1.0 MB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/mart_ng911_fresno_esb.parquet`
- **NENA SSAP Address Points with Dispatch Routing (16 MB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/mart_ng911_fresno_ssap.parquet`
- **NENA Road Centerlines (6.7 MB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/mart_ng911_fresno_rcl.parquet`
- **QA/QC Fishbone Vectors (8.0 MB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/mart_ng911_fresno_fishbones.parquet`
- **Regional Central Valley Addresses (15.5 MB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/regional_central_valley_addresses.parquet`
- **NENA v3.0 AdPt Normalized (16.8 MB GeoParquet):**
  `https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output/nena_v3/mart_nena3_adpt.parquet`

---

## Key Compliance & Architectural Highlights

1. **Dual-Model Support:**
   - **NENA v3.0 Relational Data Model (`NENA-STA-006.3-2026`)**: Fully normalized 3NF enterprise data store for Core NG9-1-1 Location Validation (LVF) and Emergency Call Routing (ECRF).
   - **NENA-STA-010 GIS Exchange Model**: Flat, streaming GeoParquet layers for zero-install analytics and GeoLibre visualization.
2. **Cal OES 98% Transition Readiness Audit Mart (`mart_ng911_qa_readiness_audit`):**
   - Automatically checks $\ge 98\%$ RCL snapping compliance within 50m.
   - Audits $100\%$ PSAP boundary coverage.
   - Asserts zero address range inversions across all centerline segments.
3. **ODbL Licensing Isolation:** 100% of the geometry in the Road Centerlines and Address marts belongs to authoritative County GIS. Overture/OSM geometry is strictly isolated to read-only QA/QC comparison.
4. **Automated Testing:** 83 automated dbt tests asserting schema constraints, uniqueness, not-null requirements, and foreign key referential integrity.
