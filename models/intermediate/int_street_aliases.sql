{{ config(materialized='table') }}

-- Alias street names for road segments: every name on a shared geometry other than the
-- primary chosen in int_road_centerlines.
SELECT DISTINCT
    s.street_segment_id,
    s.pre_directional,
    s.street_name,
    s.street_type,
    s.post_directional,
    s.full_street_name
FROM {{ ref('stg_county_streets') }} s
JOIN {{ ref('int_road_centerlines') }} p USING (street_segment_id)
WHERE s.full_street_name <> p.full_street_name
