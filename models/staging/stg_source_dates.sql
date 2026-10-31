{{ config(materialized='view') }}

-- Last data edit per source layer, written by scripts/run_pilot.py (source_freshness) before dbt runs.
-- Used for NENA DateUpdate where the source has no per-record edit date.
SELECT s.source, s.last_published::DATE AS last_published
FROM (SELECT unnest(sources) AS s FROM read_json_auto('data/output/source_freshness.json'))
