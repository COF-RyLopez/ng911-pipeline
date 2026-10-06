{{ config(
    materialized='table'
) }}

WITH raw_county AS (
    SELECT
        county_id,
        house_number AS raw_hno,
        street_name AS raw_stn,
        street_type AS raw_sts,
        community_name AS raw_muni,
        longitude AS raw_lon,
        latitude AS raw_lat,
        geom AS raw_geom
    FROM {{ ref('stg_county_addresses') }}
),

enhanced_ng911 AS (
    SELECT
        CountyLocalID,
        SSAP_NGUID,
        HNO AS enhanced_hno,
        STN AS enhanced_stn,
        STS AS enhanced_sts,
        Muni AS enhanced_muni,
        PSAP,
        PSAP_NGUID,
        PSAP_Phone,
        ESB_Fire,
        LandmarkName,
        LandmarkCategory,
        Longitude AS enhanced_lon,
        Latitude AS enhanced_lat,
        ConflationStatus,
        SpatialOffsetMeters,
        ST_Geometry AS enhanced_geom
    FROM {{ ref('mart_ng911_addresses') }}
)

SELECT
    e.SSAP_NGUID,
    r.county_id AS CountyLocalID,
    
    -- Raw Input Attributes
    r.raw_hno || ' ' || r.raw_stn || coalesce(' ' || r.raw_sts, '') AS RawAddress,
    r.raw_lon AS RawLongitude,
    r.raw_lat AS RawLatitude,
    
    -- Enhanced NG911 Attributes
    e.enhanced_hno || ' ' || e.enhanced_stn || coalesce(' ' || e.enhanced_sts, '') AS EnhancedAddress,
    e.enhanced_lon AS EnhancedLongitude,
    e.enhanced_lat AS EnhancedLatitude,
    e.PSAP,
    e.PSAP_NGUID,
    e.PSAP_Phone,
    e.ESB_Fire,
    e.LandmarkName,
    e.LandmarkCategory,
    e.ConflationStatus,

    -- Spatial Offset / Displacement calculation
    round(cast(ST_Distance(r.raw_geom, e.enhanced_geom) * 111320.0 as double), 2) AS DisplacementMeters,

    -- Categorize primary enhancement type
    CASE
        WHEN (ST_Distance(r.raw_geom, e.enhanced_geom) * 111320.0) > 5.0 THEN 'SPATIAL_CORRECTION'
        WHEN e.LandmarkName IS NOT NULL THEN 'LANDMARK_ALIASED'
        WHEN e.PSAP IS NOT NULL THEN 'PSAP_ENRICHMENT'
        WHEN (r.raw_hno || ' ' || r.raw_stn) != (e.enhanced_hno || ' ' || e.enhanced_stn) THEN 'NENA_STREET_NORMALIZED'
        ELSE 'UNCHANGED'
    END AS EnhancementCategory,

    -- Geometry representation for visual vector diffing (LineString from Raw to Enhanced)
    ST_MakeLine(r.raw_geom, e.enhanced_geom) AS DiffLineGeom,
    e.enhanced_geom AS ST_Geometry

FROM raw_county r
INNER JOIN enhanced_ng911 e ON r.county_id = e.CountyLocalID
