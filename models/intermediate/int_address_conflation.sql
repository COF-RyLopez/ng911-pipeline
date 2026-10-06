{{ config(materialized='view') }}

WITH county_stg AS (
    SELECT * FROM {{ ref('stg_county_addresses') }}
),

overture_stg AS (
    SELECT * FROM {{ ref('stg_overture_addresses') }}
),

-- 1. Identify candidate spatial & attribute matches
matched_pairs AS (
    SELECT
        c.county_id,
        o.overture_id,
        ST_Distance(c.geom, o.geom) * 111320.0 AS spatial_offset_meters,
        ROW_NUMBER() OVER (
            PARTITION BY c.county_id 
            ORDER BY ST_Distance(c.geom, o.geom) ASC
        ) AS county_rn,
        ROW_NUMBER() OVER (
            PARTITION BY o.overture_id 
            ORDER BY ST_Distance(c.geom, o.geom) ASC
        ) AS overture_rn
    FROM county_stg c
    INNER JOIN overture_stg o
        ON c.house_number = o.house_number
       AND ST_DWithin(c.geom, o.geom, {{ var('conflation_distance_degrees', 0.00015) }})
),

-- Deduplicate matches to best 1-to-1 pairs
best_matches AS (
    SELECT
        county_id,
        overture_id,
        spatial_offset_meters
    FROM matched_pairs
    WHERE county_rn = 1 AND overture_rn = 1
),

-- 2. Conflated Records (Municipal data augmented with Overture GERS ID)
conflated_records AS (
    SELECT
        'CONFLATED' AS conflation_status,
        c.county_id,
        m.overture_id AS gers_id,
        c.house_number,
        c.house_number_suffix,
        c.pre_directional,
        c.street_name,
        c.street_type,
        c.post_directional,
        c.unit,
        c.community_name,
        c.postcode,
        c.county,
        c.state,
        c.country,
        c.longitude,
        c.latitude,
        c.geom,
        round(m.spatial_offset_meters, 2) AS spatial_offset_meters,
        c.source_agency
    FROM county_stg c
    INNER JOIN best_matches m ON c.county_id = m.county_id
),

-- 3. County-Only Records (Authoritative local records absent from Overture)
county_only_records AS (
    SELECT
        'COUNTY_ONLY' AS conflation_status,
        c.county_id,
        NULL::VARCHAR AS gers_id,
        c.house_number,
        c.house_number_suffix,
        c.pre_directional,
        c.street_name,
        c.street_type,
        c.post_directional,
        c.unit,
        c.community_name,
        c.postcode,
        c.county,
        c.state,
        c.country,
        c.longitude,
        c.latitude,
        c.geom,
        NULL::DOUBLE AS spatial_offset_meters,
        c.source_agency
    FROM county_stg c
    LEFT JOIN best_matches m ON c.county_id = m.county_id
    WHERE m.county_id IS NULL
),

-- 4. Overture-Only Records (Overture addresses unverified by County GIS)
overture_only_records AS (
    SELECT
        'OVERTURE_ONLY' AS conflation_status,
        NULL::VARCHAR AS county_id,
        o.overture_id AS gers_id,
        o.house_number,
        NULL::VARCHAR AS house_number_suffix,
        o.pre_directional,
        o.street_name,
        o.street_type,
        NULL::VARCHAR AS post_directional,
        NULL::VARCHAR AS unit,
        o.community_name,
        o.postcode,
        o.county,
        o.state,
        o.country,
        o.longitude,
        o.latitude,
        o.geom,
        NULL::DOUBLE AS spatial_offset_meters,
        'OVERTURE' AS source_agency
    FROM overture_stg o
    LEFT JOIN best_matches m ON o.overture_id = m.overture_id
    WHERE m.overture_id IS NULL
)

SELECT * FROM conflated_records
UNION ALL
SELECT * FROM county_only_records
UNION ALL
SELECT * FROM overture_only_records
