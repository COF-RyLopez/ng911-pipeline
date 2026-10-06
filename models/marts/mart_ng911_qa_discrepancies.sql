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

-- 1. Name Mismatches: Close proximity but conflicting street names (NENA 02-014.1 Sec 4.3.3)
name_discrepancies AS (
    SELECT
        'NAME_MISMATCH' AS DiscrepancyType,
        'MEDIUM' AS Severity,
        c.street_segment_id AS CountyFeatureID,
        o.overture_segment_id AS OvertureFeatureID,
        c.street_name AS CountyValue,
        o.road_name AS OvertureValue,
        'Street name in County GIS differs from Overture/OSM reference network' AS Description,
        c.geom AS ST_Geometry
    FROM county_streets c
    INNER JOIN overture_roads o
        ON c.gx = o.gx AND c.gy = o.gy
       AND ST_DWithin(c.geom, o.geom, {{ var('conflation_distance_degrees', 0.00015) }} * 2)
       AND c.street_name != o.road_name
),

-- 2. Potential Missing Roads: Overture roads with no matching County centerline within 50m (NENA 02-014.1 Sec 4.3.2)
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
),

-- 3. Unprovisionable Records: Missing house number or street name (NENA STA-005.1.2 Sec 5.4.1)
unprovisionable_records AS (
    SELECT
        'UNPROVISIONABLE_RECORD' AS DiscrepancyType,
        'CRITICAL' AS Severity,
        county_id AS CountyFeatureID,
        NULL::VARCHAR AS OvertureFeatureID,
        coalesce(house_number, '') || ' ' || coalesce(street_name, '') AS CountyValue,
        NULL::VARCHAR AS OvertureValue,
        'Address record cannot be provisioned to ECRF/LVF due to missing house number or street name' AS Description,
        geom AS ST_Geometry
    FROM {{ ref('stg_county_addresses') }}
    WHERE house_number IS NULL OR trim(house_number) = ''
       OR street_name IS NULL OR trim(street_name) = ''
),

-- 4. Civic Address Ambiguity: Duplicate address points sharing house number, street name, and community (NENA STA-005.1.2 Sec 7)
ambiguous_addresses AS (
    SELECT
        'CIVIC_ADDRESS_AMBIGUITY' AS DiscrepancyType,
        'HIGH' AS Severity,
        a.SSAP_NGUID AS CountyFeatureID,
        NULL::VARCHAR AS OvertureFeatureID,
        a.HNO || ' ' || a.STN || ' (' || a.CommunityName || ')' AS CountyValue,
        NULL::VARCHAR AS OvertureValue,
        'Multiple SSAP address points share the identical house number, street name, and community' AS Description,
        a.ST_Geometry
    FROM {{ ref('mart_ng911_addresses') }} a
    INNER JOIN (
        SELECT HNO, STN, CommunityName
        FROM {{ ref('mart_ng911_addresses') }}
        WHERE HNO IS NOT NULL AND STN IS NOT NULL
        GROUP BY HNO, STN, CommunityName
        HAVING count(*) > 5
    ) d ON a.HNO = d.HNO AND a.STN = d.STN AND a.CommunityName = d.CommunityName
),

-- 5. Excessive Offset Discrepancies: Address points positioned >50m from centerline (NENA 02-014.1 Sec 4.3)
excessive_offsets AS (
    SELECT
        'EXCESSIVE_OFFSET_DISCREPANCY' AS DiscrepancyType,
        'MEDIUM' AS Severity,
        f.SSAP_NGUID AS CountyFeatureID,
        f.RCL_NGUID AS OvertureFeatureID,
        round(f.DistanceMeters, 1)::VARCHAR || ' m' AS CountyValue,
        'Max Threshold: 50.0 m' AS OvertureValue,
        'SSAP address point spatial offset from nearest centerline segment exceeds 50 meters' AS Description,
        f.ST_Geometry
    FROM {{ ref('mart_ng911_qa_fishbones') }} f
    WHERE f.IsExcessiveOffset = TRUE
)

SELECT * FROM name_discrepancies
UNION ALL
SELECT * FROM missing_roads
UNION ALL
SELECT * FROM unprovisionable_records
UNION ALL
SELECT * FROM ambiguous_addresses
UNION ALL
SELECT * FROM excessive_offsets
