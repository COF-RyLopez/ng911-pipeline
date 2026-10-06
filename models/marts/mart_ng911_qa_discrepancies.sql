{{ config(
    materialized='table'
) }}

WITH county_streets AS (
    SELECT 
        street_segment_id, 
        street_name, 
        geom,
        floor(ST_X(ST_Centroid(geom)) * 50)::INTEGER AS gx,
        floor(ST_Y(ST_Centroid(geom)) * 50)::INTEGER AS gy
    FROM {{ ref('stg_county_streets') }}
),

overture_roads AS (
    SELECT 
        overture_segment_id, 
        road_name, 
        geom,
        floor(ST_X(ST_Centroid(geom)) * 50)::INTEGER AS gx,
        floor(ST_Y(ST_Centroid(geom)) * 50)::INTEGER AS gy
    FROM {{ ref('stg_overture_transportation') }}
    WHERE road_name IS NOT NULL
),

-- 1. Name Mismatches: Close proximity but conflicting names
name_discrepancies AS (
    SELECT
        'NAME_MISMATCH' AS DiscrepancyType,
        'MEDIUM' AS Severity,
        c.street_segment_id AS CountyFeatureID,
        o.overture_segment_id AS OvertureFeatureID,
        c.street_name AS CountyValue,
        o.road_name AS OvertureValue,
        'Street name in County GIS differs from Overture/OSM name' AS Description,
        c.geom AS ST_Geometry
    FROM county_streets c
    INNER JOIN overture_roads o
        ON c.gx = o.gx AND c.gy = o.gy
       AND ST_DWithin(c.geom, o.geom, {{ var('conflation_distance_degrees', 0.00015) }} * 2)
       AND c.street_name != o.road_name
),

-- 2. Potential Missing Roads: Overture roads with no County centerline within 50m in same grid bucket
missing_roads AS (
    SELECT
        'POTENTIAL_MISSING_ROAD' AS DiscrepancyType,
        'HIGH' AS Severity,
        NULL::VARCHAR AS CountyFeatureID,
        o.overture_segment_id AS OvertureFeatureID,
        NULL::VARCHAR AS CountyValue,
        o.road_name AS OvertureValue,
        'Overture road segment has no matching County street centerline within 50 meters' AS Description,
        o.geom AS ST_Geometry
    FROM overture_roads o
    LEFT JOIN county_streets c
        ON o.gx = c.gx AND o.gy = c.gy
       AND ST_DWithin(o.geom, c.geom, {{ var('conflation_distance_degrees', 0.00015) }} * 3)
    WHERE c.street_segment_id IS NULL
)

SELECT * FROM name_discrepancies
UNION ALL
SELECT * FROM missing_roads
