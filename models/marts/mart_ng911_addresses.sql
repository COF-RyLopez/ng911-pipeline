{{ config(
    materialized='table'
) }}

WITH conflated_data AS (
    SELECT * FROM {{ ref('int_address_conflation') }}
)

SELECT
    -- 1. NENA Mandatory Agency and Globally Unique Identifiers
    '{{ var("agency_domain", "fresnocountyca.gov") }}' AS DisclID,
    'urn:emergency:uid:gis:SSAP:' || coalesce(county_id, gers_id) || ':{{ var("agency_domain", "fresnocountyca.gov") }}' AS SSAP_NGUID,

    -- 2. External Federation & Conflation Lineage Identifiers
    county_id AS CountyLocalID,
    gers_id AS GERS_ID,
    conflation_status AS ConflationStatus,
    CASE conflation_status
        WHEN 'CONFLATED' THEN 'FRESNO_COUNTY_GIS_OVERTURE_CONFLATED'
        WHEN 'COUNTY_ONLY' THEN 'FRESNO_COUNTY_GIS'
        WHEN 'OVERTURE_ONLY' THEN 'OVERTURE_MAPS'
    END AS Source,

    -- 3. NENA-STA-010 Standardized Road Character Attributes (SSAP)
    upper(house_number) AS HNO,
    upper(house_number_suffix) AS HNS,
    upper(pre_directional) AS PRD,
    upper(street_name) AS STN,
    upper(street_type) AS STS,
    upper(post_directional) AS POD,
    upper(unit) AS Unit,

    -- 4. Jurisdictional & Postal Attributes
    upper(community_name) AS CommunityName,
    upper(county) AS County,
    upper(state) AS State,
    postcode AS PostCode,
    upper(country) AS Country,

    -- 5. Explicit Geospatial Coordinates for Dispatch Telematics
    longitude AS Longitude,
    latitude AS Latitude,

    -- 6. Spatial Discrepancy & Routing Quality Indicators
    spatial_offset_meters AS SpatialOffsetMeters,
    current_timestamp AS DateUpdate,

    -- 7. Native Geometry (Point / WKB)
    geom AS ST_Geometry

FROM conflated_data
