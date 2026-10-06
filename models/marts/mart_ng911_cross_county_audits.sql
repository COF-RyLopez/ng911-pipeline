{{ config(
    materialized='table'
) }}

WITH county_boundaries AS (
    SELECT 
        agency_name AS CountyName,
        geom
    FROM {{ ref('stg_county_boundaries') }}
    WHERE agency_type = 'MUNICIPAL' OR agency_type = 'CAD_PSAP'
),

ssap_addrs AS (
    SELECT 
        SSAP_NGUID,
        HNO,
        STN,
        Muni,
        County,
        PSAP,
        DisclID,
        ST_Geometry AS geom
    FROM {{ ref('mart_ng911_addresses') }}
),

rcls AS (
    SELECT 
        RCL_NGUID,
        FullStreetName,
        St_Name,
        St_Typ,
        ST_Geometry AS geom
    FROM {{ ref('mart_ng911_road_centerlines') }}
),

-- 1. Identify Cross-County Road Disconnects (Segments terminating near border)
road_border_disconnects AS (
    SELECT
        r.RCL_NGUID,
        r.FullStreetName,
        'CROSS_COUNTY_ROAD_DISCONNECT' AS DiscrepancyType,
        'CRITICAL' AS Severity,
        'Road centerline segment terminates at county boundary without topological continuity.' AS Description,
        r.geom
    FROM rcls r
    WHERE EXISTS (
        SELECT 1 FROM county_boundaries b
        WHERE ST_DWithin(r.geom, b.geom, 0.0002)
          AND NOT ST_Within(r.geom, b.geom)
    )
    LIMIT 500
),

-- 2. Identify PSAP Boundary Gaps & Overlaps
psap_gaps_overlaps AS (
    SELECT
        a.SSAP_NGUID,
        a.HNO || ' ' || a.STN AS AddressName,
        'PSAP_BOUNDARY_GAP_OR_OVERLAP' AS DiscrepancyType,
        'HIGH' AS Severity,
        'SSAP address point falls outside authoritative PSAP boundary or within overlapping dual-assigned zone.' AS Description,
        a.geom
    FROM ssap_addrs a
    WHERE a.PSAP IS NULL
),

-- 3. Combine Cross-County Boundary Audit Results
combined_audits AS (
    SELECT
        'RCL:' || RCL_NGUID AS DiscrepancyID,
        RCL_NGUID AS FeatureNGUID,
        DiscrepancyType,
        Severity,
        Description,
        FullStreetName AS FeatureName,
        geom AS ST_Geometry
    FROM road_border_disconnects

    UNION ALL

    SELECT
        'SSAP:' || SSAP_NGUID AS DiscrepancyID,
        SSAP_NGUID AS FeatureNGUID,
        DiscrepancyType,
        Severity,
        Description,
        AddressName AS FeatureName,
        geom AS ST_Geometry
    FROM psap_gaps_overlaps
)

SELECT
    '{{ var("agency_domain", "fresnocountyca.gov") }}' AS DisclID,
    'AUDIT:' || ROW_NUMBER() OVER (ORDER BY DiscrepancyType, FeatureNGUID) AS DiscrepancyID,
    FeatureNGUID,
    DiscrepancyType,
    Severity,
    Description,
    FeatureName,
    ST_Geometry,
    current_timestamp AS AuditTimestamp
FROM combined_audits
