{{ config(
    materialized='table'
) }}

WITH addresses AS (
    SELECT
        CountyLocalID,
        SSAP_NGUID,
        HNO,
        PRD,
        STN,
        STS,
        POD,
        Muni,
        CommunityName,
        PSAP,
        ESB_Fire,
        LandmarkName,
        SpatialOffsetMeters,
        Longitude AS enhanced_lon,
        Latitude AS enhanced_lat,
        ST_Geometry AS enhanced_geom,
        cast(floor(Longitude * 200.0) as int) AS grid_x,
        cast(floor(Latitude * 200.0) as int) AS grid_y
    FROM {{ ref('mart_ng911_addresses') }}
),

raw_inputs AS (
    SELECT
        county_id,
        house_number AS raw_hno,
        street_name AS raw_stn,
        street_type AS raw_sts,
        longitude AS raw_lon,
        latitude AS raw_lat,
        geom AS raw_geom
    FROM {{ ref('stg_county_addresses') }}
),

buildings AS (
    SELECT building_id, geom, grid_x, grid_y FROM {{ ref('stg_overture_buildings') }}
),

building_intersection AS (
    SELECT DISTINCT
        a.SSAP_NGUID
    FROM addresses a
    INNER JOIN raw_inputs r ON a.CountyLocalID = r.county_id
    JOIN buildings b 
      ON a.grid_x = b.grid_x 
     AND a.grid_y = b.grid_y
     AND ST_Intersects(a.enhanced_geom, b.geom)
),

discrepancies AS (
    SELECT
        CountyFeatureID,
        DiscrepancyType,
        Severity,
        Description
    FROM {{ ref('mart_ng911_qa_discrepancies') }}
)

SELECT
    a.SSAP_NGUID,
    a.CountyLocalID,
    r.raw_hno AS OriginalHouseNumber,
    r.raw_stn AS OriginalStreetName,
    a.HNO || ' ' || a.STN || coalesce(' ' || a.STS, '') AS StandardizedAddress,
    a.CommunityName,
    r.raw_lon AS CurrentLongitude,
    r.raw_lat AS CurrentLatitude,
    a.enhanced_lon AS RemediatedLongitude,
    a.enhanced_lat AS RemediatedLatitude,
    a.SpatialOffsetMeters AS SpatialOffsetMeters,

    CASE
        WHEN bi.SSAP_NGUID IS NOT NULL THEN 'INSIDE_BUILDING_FOOTPRINT'
        ELSE 'OUTSIDE_BUILDING_FOOTPRINT'
    END AS BuildingFootprintStatus,

    coalesce(d.DiscrepancyType, 'NONE') AS DiscrepancyType,
    coalesce(d.Severity, 'OK') AS Severity,

    -- Symbology Category Code for GeoLibre map rendering
    CASE
        WHEN d.Severity IN ('CRITICAL', 'HIGH') THEN 'CRITICAL_ATTENTION'
        WHEN bi.SSAP_NGUID IS NULL AND a.SpatialOffsetMeters > 25.0 THEN 'OUTSIDE_BUILDING'
        WHEN d.DiscrepancyType IS NOT NULL THEN 'ATTENTION_REQUIRED'
        ELSE 'VALIDATED_OK'
    END AS SymbologyCategory,

    -- Mapillary Street-Level View direct URL at address location for ground-truth verification
    'https://www.mapillary.com/app/?lat=' || cast(a.enhanced_lat as varchar) || '&lng=' || cast(a.enhanced_lon as varchar) || '&z=18' AS MapillaryGroundTruthURL,

    -- Actionable Fix Guidance for Jurisdiction GIS Analysts
    CASE
        WHEN d.DiscrepancyType = 'EXCESSIVE_OFFSET' THEN 'Relocate address point to driveway access or structure centroid (offset >50m)'
        WHEN d.DiscrepancyType = 'CIVIC_ADDRESS_AMBIGUITY' THEN 'Assign unit/suite numbers to resolve duplicate address points'
        WHEN bi.SSAP_NGUID IS NULL THEN 'Address point is outside building footprint; inspect aerial/Mapillary imagery to verify placement'
        WHEN a.PSAP IS NULL THEN 'Verify municipal boundary for PSAP dispatch assignment'
        ELSE 'Address validated against NENA v3 standards'
    END AS RecommendedRemediationAction,

    a.enhanced_geom AS ST_Geometry

FROM addresses a
INNER JOIN raw_inputs r ON a.CountyLocalID = r.county_id
LEFT JOIN building_intersection bi ON a.SSAP_NGUID = bi.SSAP_NGUID
LEFT JOIN discrepancies d ON a.CountyLocalID = d.CountyFeatureID OR a.SSAP_NGUID = d.CountyFeatureID
