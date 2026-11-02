# Open-data NG9-1-1 for California

How far can open data get every California county toward a NENA NG9-1-1 GIS dataset? This repo builds
address points and road centerlines for all 58 counties from [Overture Maps](https://overturemaps.org)
alone, checks them against the road network, publishes them as two prototype **GERS Extensions** in the
NENA NG9-1-1 GIS Data Model (**NENA-STA-006.3-2026**) shape, and sets them next to a full county-GIS build
for Fresno.

## The three apps

Published by CI to Cloudflare R2. The landing page links all three:
**https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/apps.html**

| App | Link | Shows |
|---|---|---|
| 1 · Open data only | [`index.html?app=open`](https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/index.html?app=open) | Statewide readiness by county; all 58 counties built from Overture, each address checked against a same-named road; Overture roads with address ranges derived from those addresses |
| 2 · County sources | [`index.html?app=county`](https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/index.html?app=county) | Fresno County's own address, road, parcel and boundary layers vs Overture and the state (CDTFA), plus OpenStreetMap road fixes |
| 3 · Remediation | [`index.html`](https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/index.html) | The full Fresno hub: Cal OES readiness gates, address-to-road links, buildings, parcels, street imagery and fix changesets |

## Open data only: all 58 counties

- `scripts/statewide_overture_scorecard.py` scores every county on Overture address completeness and named
  public roads (`statewide/ca_overture_county_scorecard.{csv,geojson}`).
- `scripts/overture_only_counties.py` runs the `models/overture_only/oo_*` dbt models for every county:
  address points parsed into NENA street parts, Overture road centerlines, and an address-to-road check (the
  nearest same-named road within ~400 m; "OK" within 50 m). Counties built from county GIS (Fresno, Kings)
  get an Overture-only build too, for comparison.
- Statewide (Overture release 2026-09-23.1): about 13.6 million addresses and 1.65 million named road
  segments; in most counties 80–99% of addresses match a same-named road.

## GERS Extensions (prototype)

Two packages add NENA properties to Overture features as columns keyed on the GERS ID, following the
Overture GERS Extensions framework (properties not features, GERS ID join key, no redefined reference
properties, declared schema range, a sample that parses). Each ships its NENA-STA-006.3 coded domains and a
conformance test suite that runs in CI.

| Package | Extends | Adds | Data |
|---|---|---|---|
| [`extensions/ng911-address`](extensions/ng911-address) | `addresses/address` | NENA Site/Structure Address Point fields: street parts as NENA registry words, unit, postal fields, NGUID, the road check | [`ng911_address_ca.parquet`](https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/extensions/ng911_address/ng911_address_ca.parquet) · [manifest](https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/extensions/ng911_address/manifest.json) |
| [`extensions/ng911-road-centerline`](extensions/ng911-road-centerline) | `transportation/segment` | NENA Road Centerline fields: left/right address ranges and parity derived from matched addresses, NENA road class, street parts | [`ng911_road_centerline_ca.parquet`](https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/extensions/ng911_road_centerline/ng911_road_centerline_ca.parquet) · [manifest](https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/extensions/ng911_road_centerline/manifest.json) |

Each manifest reports rows, GERS ID coverage against the stated Overture release, per-field fill, and the
NENA marks: the share of records carrying every mandatory field and any street type not in the NENA
registry. Join to Overture on `id`:

```sql
SELECT a.id, a.number, a.street, e.ng911.st_name, e.ng911.st_postyp, e.ng911.road_match
FROM read_parquet('s3://overturemaps-us-west-2/release/2026-09-23.1/theme=addresses/type=address/*.parquet') a
JOIN read_parquet('https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/extensions/ng911_address/ng911_address_ca.parquet') e USING (id)
WHERE a.bbox.xmin BETWEEN -124.5 AND -114.1 AND a.bbox.ymin BETWEEN 32.5 AND 42.1
LIMIT 10;
```

Not in open data, so not filled: PSAP/fire/EMS/law boundaries, ESN and MSAG communities, incorporated
municipality (A3), and the 9-1-1 authority's agency domain (a placeholder until an authority publishes).

## Fixing open data

Value fixes (zero-padded ordinals, abbreviated name words, odd street types) happen in our parse, as the
OpenAddresses maintainers prefer. Wrong field mappings or filters in an OpenAddresses source are fixed
upstream with a PR. `scripts/oa_conform_audit.py` checks every California OpenAddresses source for them.

## How it runs

- `.github/workflows/ci.yml` runs on every PR and on `main`: the county jobs (Fresno, Kings) and a parallel
  Overture-only job (statewide scorecard, 58 counties, Extension datasets and conformance tests, map tiles).
- Only `main` publishes to R2; each job publishes and prunes only its own files.
- Locally: `uv pip install dbt-duckdb duckdb pyarrow pandas boto3 tylertoo overture-schema`, then the
  scripts above. See [`AGENTS.md`](AGENTS.md) for the details (DuckDB 2.0 notes, running one county,
  publishing).

---

## The Fresno county-GIS build (App 3)

An end-to-end Python, DuckDB, and dbt pipeline designed to ingest municipal and county GIS endpoints across California's Central Valley (**Fresno**, **Kings**, and **Tulare** Counties), conflate them with Overture Maps global GeoParquet data, and structure them natively into a **Dual-Model NG9-1-1 Architecture**:
1. **Model A — NENA v3.0 Relational Data Model (NENA-STA-006.x)**: Fully normalized 3NF relational schema matching the official [NENA GIS Data Model v3.0](https://github.com/NENA911/NG911GISDataModel/blob/main/relational_templates/schema/v3.0/README.md).
2. **Model B — NENA-STA-010 GIS Exchange Model**: Optimized flat GeoParquet layers for zero-install streaming in [GeoLibre](https://web.geolibre.app/), QGIS, CAD/PSAP integration, and automated **Cal OES 98% Transition Readiness Auditing**.

### Dual-Model Architecture & Directory Structure

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
│   │   ├── stg_county_streets.sql         # Road centerlines from OpenAddresses county sources (Fresno 53k; +Kings/Tulare with published ranges)
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

### Setup & Prerequisites

1. Ensure Python 3.12+ and virtual environment are configured:
   ```bash
   uv venv --python 3.12
   uv pip install --python .venv dbt-duckdb pandas
   ```

---

### Running the Pilot Pipeline

To execute the entire pilot end-to-end (ingest, dbt transformation, 83 data quality tests, and GIS exports):

```bash
./.venv/bin/python scripts/run_pilot.py
```

#### Running Individual Pipeline Stages

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

### Multi-County Regional Metrics (Central Valley)

| County | Authoritative Address Count | Ingestion Method | Status |
| :--- | :--- | :--- | :--- |
| **Fresno County** | **395,107** (466,751 total SSAP) | ArcGIS Hub `REGIONAL_ADDRESS_VW` (Active + Current + Pending) | Verified Authoritative |
| **Tulare County** | **170,483** | Open Data FeatureServer | Verified Authoritative |
| **Kings County** | **51,877** | Parallel REST Server | Verified Authoritative |
| **Total Central Valley** | **617,467 addresses** | High-Speed Stream Ingest | **100% Authoritative** |

---

### Official NENA v3.0 Relational Model (NENA-STA-006.x)

Deliverables exported to `data/output/nena_v3/`:
- **`mart_nena3_adpt.parquet` (618,633 rows, 26.0 MB)**: Normalized 3NF address points linking foreign keys to `DiscrpAg_ID`, `CompleteStNam_ID`, and `CompleteAdNum_ID`.
- **`mart_nena3_stseg.parquet` (53,576 rows, 6.6 MB)**: Street centerline segments with 3NF foreign keys to `CompleteStNam_ID` and `DiscrpAg_ID`.
- **`mart_nena3_serviceboundary.parquet` (80 rows, 1.0 MB)**: MultiPolygon emergency service boundaries referencing `ServiceURN_ID` and `DiscrpAg_ID`.
- **`mart_nena3_completestnam.parquet` (12,708 rows)**: Normalized street components (`St_PreDir`, `St_Name`, `St_Typ`, `St_PosDir`).
- **`mart_nena3_completeadnum.parquet` (37,249 rows)**: Normalized address numbers (`Add_Number`, `AddNum_Suf`).
- **`mart_nena3_discrpag.parquet` (3 rows)**: Authority registry (`fresnocountyca.gov`, `kingscountyca.gov`, `tularecountyca.gov`).
- **`mart_nena3_serviceurn.parquet` (4 rows)**: RFC 5031 service identifiers (`sos`, `sos.fire`, `sos.police`, `sos.ambulance`).

---

### Zero-Install GIS Viewing & Statewide Sharing via GeoLibre

To allow anyone—especially non-ESRI agencies and dispatch centers across California—to inspect the pilot results without installing desktop GIS software:

#### Option 1: 1-Click Complete Map Project
Open the pre-styled, self-contained project (amber boundary polygons, green centerlines, blue address points with dispatch popups, red fishbones, and a 3-widget dashboard) directly in GeoLibre:
```text
https://web.geolibre.app/?url=https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/fresno_ng911_pilot.geolibre.json
```
*(Outputs are rebuilt by CI on every push to `main` and published to Cloudflare R2; they are not committed to git. After a local `run_pilot.py`, you can also drag `data/output/fresno_ng911_pilot.geolibre.json` into [web.geolibre.app](https://web.geolibre.app/).)*

#### Option 2: 1-Click Visual Address QA/QC & BYOD Comparison Hub
Open the interactive visual comparison project comparing raw municipal addresses vs NG911 enhanced addresses (with displacement vector lines and color-coded enhancement categories):
```text
https://web.geolibre.app/?url=https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/ng911_address_comparison_r2.geolibre.json
```

**Bring Your Own Data (BYOD) Local Comparison:**
Generate a 1-click comparison project for any local user address dataset (`.csv`, `.geojson`, `.parquet`):
```bash
./.venv/bin/python scripts/generate_comparison_geolibre_project.py --source-file path/to/local_addresses.geojson
```

#### Option 3: Additive Layer Streaming (No Workspace Reset)
In GeoLibre, open **Add Vector Layer**, paste any of the public Cloudflare R2 endpoints below, and check **"Stream GeoParquet (no copy)"**:
- **NENA Emergency Service Boundaries (1.0 MB GeoParquet):**
  `https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/mart_ng911_fresno_esb.parquet`
- **NENA SSAP Address Points with Dispatch Routing (16 MB GeoParquet):**
  `https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/mart_ng911_fresno_ssap.parquet`
- **Address Enhancements & QA/QC Displacement (17 MB GeoParquet):**
  `https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/mart_ng911_fresno_enhancements.parquet`
- **NENA Road Centerlines (6.7 MB GeoParquet):**
  `https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/mart_ng911_fresno_rcl.parquet`
- **QA/QC Fishbone Vectors (8.0 MB GeoParquet):**
  `https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/mart_ng911_fresno_fishbones.parquet`
- **Regional Central Valley Addresses (15.5 MB GeoParquet):**
  `https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/regional_central_valley_addresses.parquet`
- **NENA v3.0 AdPt Normalized (16.8 MB GeoParquet):**
  `https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/nena_v3/mart_nena3_adpt.parquet`


---

### Key Compliance & Architectural Highlights

1. **Dual-Model Support:**
   - **NENA v3.0 Relational Data Model (NENA-STA-006.x)**: Fully normalized 3NF enterprise data store for Core NG9-1-1 Location Validation (LVF) and Emergency Call Routing (ECRF).
   - **NENA-STA-010 GIS Exchange Model**: Flat, streaming GeoParquet layers for zero-install analytics and GeoLibre visualization.
2. **Cal OES 98% Transition Readiness Audit Mart (`mart_ng911_qa_readiness_audit`):**
   - Checks that $\ge 98\%$ of address points (county and Overture) match a same-named road centerline (within ~400 m), and reports the share within 50 m as a review metric.
   - Checks $\ge 98\%$ dispatch (PSAP stand-in) coverage of authoritative address points.
   - Asserts zero address range inversions across all centerline segments.
3. **ODbL Licensing Isolation:** 100% of the geometry in the Road Centerlines and Address marts belongs to authoritative County GIS. Overture/OSM geometry is strictly isolated to read-only QA/QC comparison.
4. **Automated Testing:** 83 automated dbt tests asserting schema constraints, uniqueness, not-null requirements, and foreign key referential integrity.
