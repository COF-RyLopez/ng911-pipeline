{{ config(materialized='table') }}

WITH raw_buildings AS (
    SELECT *
    FROM read_parquet('data/cache/overture_buildings.parquet')
)

SELECT
    building_id,
    height,
    num_floors,
    building_class,
    geom
FROM raw_buildings
WHERE geom IS NOT NULL
