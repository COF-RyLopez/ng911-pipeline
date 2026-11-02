# AGENTS.md

Guidance for coding agents working in this repo. Keep it short and true; update it when something here
stops being right.

## What this is

An open-data NG9-1-1 (NENA) pipeline for California counties, in three products, each an app on the
published site (`apps.html` links them):

1. **Open data only** (`index.html?app=open`): every county built from Overture alone (addresses + roads),
   statewide scorecard, and two prototype GERS Extensions (`extensions/`).
2. **County sources** (`index.html?app=county`): a county's own GIS vs open data and the state (CDTFA).
3. **Remediation** (`index.html`): the full Fresno hub.

Published: `https://pub-152dce9299c94555bb415d992fe120e7.r2.dev/` (R2, written only by CI on `main`).

## Layout

- `models/` dbt models (dbt-duckdb). `models/overture_only/oo_*` is the Overture-only build;
  `stg_overture_addresses` parses Overture streets into NENA parts (shared by the Fresno comparison).
- `macros/geometry_helpers.sql` street parsing helpers: `street_type_suffix_regex`, `normalize_street_type`,
  `normalize_direction`, `street_match_key` (both sides of an address-to-road match go through it).
- `scripts/` Python entry points: `fetch_pilot_data.py`, `run_pilot.py`, `overture_only_counties.py`,
  `statewide_overture_scorecard.py`, `build_ng911_extension.py`, `build_pmtiles.py`, `publish_to_r2.py`.
- `extensions/ng911-address`, `extensions/ng911-road-centerline`: GERS Extension packages (Pydantic on
  `overture-schema` v2) with conformance tests and vendored NENA-STA-006.3 domains.
- `index.html` is the whole web app (MapLibre + PMTiles); `apps.html` is the landing page.

## Running things

- Python 3.12+, `uv pip install dbt-duckdb duckdb pyarrow pandas boto3 tylertoo overture-schema`.
- Overture is read anonymously from `s3://overturemaps-us-west-2/release/<release>`; the release is pinned
  in `statewide_overture_scorecard.py` and `fetch_pilot_data.py` (keep them in step).
- One county, Overture only: call `overture_only_counties.build(feature, "dbt")` with a feature from the
  statewide scorecard GeoJSON (County names end in " County"). Build in a git worktree so the main
  checkout's caches and `ng911_database.duckdb` aren't touched.
- Extension packages: `cd extensions/<pkg> && PYTHONPATH=. python tests/test_conformance.py`.

## DuckDB 2.0 gotchas (CI runs 2.0)

- `SET geometry_always_xy = true` before spatial work (lon/lat order).
- Relations have no `fetchone()`; use `.fetchall()[0]`. Finish a result before the next query.
- Lambdas are `lambda x: ...`, not `x -> ...`. There is no `initcap`.
- `ST_MakeValid` before `ST_Union_Agg` on polygons with nested parts.

## CI and publishing

- `.github/workflows/ci.yml` runs on PRs and `main`: the county matrix (06019 Fresno, 06031 Kings) and a
  parallel `overture-only` job (statewide scorecard, all 58 counties, Extension datasets + conformance).
- Only `main` publishes. Each job publishes its own R2 keys (`publish_to_r2.py --part county|overture`) and
  prunes only those: the overture part owns `statewide/`, `overture_only/`, `tiles/overture_only_*`,
  `extensions/`. A new output under another prefix belongs to the county part unless added there.
- The overture-only job takes ~30 min; check its timeout when adding work to it.

## Rules we've learned

- **Fix open data on our side.** OpenAddresses conform steps map fields; they don't rewrite values
  (maintainer, openaddresses/openaddresses#10085). Value fixes (zero-padded ordinals, abbreviations) go in
  our parse; upstream PRs are for wrong field mappings or filters.
- **NENA output uses NENA-STA-006.3-2026**: lower-cased field names (`st_postyp`, `a1`, `roadclass`),
  registry words for types/directionals ("Avenue", "North"), 0–0/Z for empty range sides. Matching keys
  can use abbreviations; the published NENA fields can't. Domains live in each package's
  `nena_sta006_3_domains.json`.
- **GERS Extensions**: properties only (no geometry), join on the GERS ID, never redefine an Overture
  property (put it under `ng911`), declare the schema range, ship a sample that parses.
- **Coverage is all 58 counties.** Don't exclude counties that also have a county-GIS build.
- Overture transportation is ODbL; keep it out of county deliverables.

## When using Bend

- run `bend guide` to learn it
- use `LAWS.bend` to keep important rules
- run `bend PROOF.bend` before committing
- parallelize the code whenever possible
