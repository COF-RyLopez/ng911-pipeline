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
    geom,
    cast(floor(ST_X(ST_Centroid(geom)) * 200.0) as int) AS grid_x,
    cast(floor(ST_Y(ST_Centroid(geom)) * 200.0) as int) AS grid_y
FROM raw_buildings
WHERE geom IS NOT NULL
