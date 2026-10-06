{{ config(materialized='view') }}

WITH raw_streets AS (
    SELECT *
    FROM read_parquet('data/cache/county_streets.parquet')
)

SELECT
    street_segment_id,
    str_id,
    agency_code,
    {{ normalize_direction('pre_directional') }} AS pre_directional,
    upper(trim(street_name)) AS street_name,
    {{ normalize_street_type('street_type') }} AS street_type,
    {{ normalize_direction('post_directional') }} AS post_directional,
    coalesce(road_class, 'Local') AS road_class,
    trim(concat_ws(' ', 
        {{ normalize_direction('pre_directional') }}, 
        upper(trim(street_name)), 
        {{ normalize_street_type('street_type') }}, 
        {{ normalize_direction('post_directional') }}
    )) AS full_street_name,
    geom
FROM raw_streets
WHERE street_name IS NOT NULL
