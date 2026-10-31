{{ config(materialized='table') }}

-- Mapillary street-level imagery coverage (sequence lines), cached by scripts/fetch_mapillary_coverage.py
SELECT captured_at, is_pano, ST_GeomFromWKB(ST_AsWKB(geom)) AS geom  -- drop the CRS84 tag so joins with untagged address points don't mismatch
FROM read_parquet('data/cache/mapillary_sequences.parquet')
WHERE geom IS NOT NULL
