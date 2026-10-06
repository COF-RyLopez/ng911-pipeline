{{ config(materialized='view') }}

WITH raw_places AS (
    SELECT *
    FROM read_parquet('data/cache/overture_places.parquet')
)

SELECT
    place_id,
    upper(trim(place_name)) AS place_name,
    lower(trim(basic_category)) AS basic_category,
    lower(trim(taxonomy_category)) AS taxonomy_category,
    confidence,
    longitude,
    latitude,
    geom
FROM raw_places
WHERE place_name IS NOT NULL 
  AND geom IS NOT NULL
