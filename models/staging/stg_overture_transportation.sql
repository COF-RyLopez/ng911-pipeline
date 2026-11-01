{{ config(materialized='view') }}

WITH raw_trans AS (
    SELECT *
    FROM read_parquet('data/cache/overture_transportation.parquet')
)

SELECT
    overture_segment_id,
    upper(trim(road_name)) AS road_name,
    road_class,
    road_subtype,
    osm_record_id,  -- lineage: OpenStreetMap way behind the segment (NULL for non-OSM sources)
    geom
FROM raw_trans
WHERE road_name IS NOT NULL
