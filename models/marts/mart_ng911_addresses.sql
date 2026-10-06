{{ config(
    materialized='table'
) }}

WITH conflated_data AS (
    SELECT 
        *,
        coalesce(county_id, gers_id) AS addr_uid
    FROM {{ ref('int_address_conflation') }}
),

boundaries AS (
    SELECT * FROM {{ ref('stg_county_boundaries') }}
),

landmarks AS (
    SELECT * FROM {{ ref('int_address_landmarks') }}
),

-- Point-in-Polygon: CAD / PSAP Boundary
addr_psap AS (
    SELECT
        c.addr_uid,
        b.agency_name AS psap_name,
        b.esb_nguid AS psap_nguid,
        b.service_number AS psap_phone,
        ROW_NUMBER() OVER (PARTITION BY c.addr_uid ORDER BY b.agency_name) AS rn
    FROM conflated_data c
    JOIN boundaries b 
      ON b.agency_type = 'PSAP' 
     AND ST_Within(c.geom, b.geom)
),

-- Point-in-Polygon: Fire District Boundary
addr_fire AS (
    SELECT
        c.addr_uid,
        b.agency_name AS esb_fire,
        b.esb_nguid AS esb_fire_nguid,
        ROW_NUMBER() OVER (PARTITION BY c.addr_uid ORDER BY b.agency_name) AS rn
    FROM conflated_data c
    JOIN boundaries b 
      ON b.agency_type = 'FIRE' 
     AND ST_Within(c.geom, b.geom)
),

-- Point-in-Polygon: Incorporated City Limits
addr_muni AS (
    SELECT
        c.addr_uid,
        b.agency_name AS muni,
        ROW_NUMBER() OVER (PARTITION BY c.addr_uid ORDER BY b.agency_name) AS rn
    FROM conflated_data c
    JOIN boundaries b 
      ON b.agency_type = 'MUNICIPAL' 
     AND ST_Within(c.geom, b.geom)
)

SELECT
    -- 1. NENA Mandatory Agency and Globally Unique Identifiers
    '{{ var("agency_domain", "fresnocountyca.gov") }}' AS DisclID,
    'urn:emergency:uid:gis:SSAP:' || c.addr_uid || ':{{ var("agency_domain", "fresnocountyca.gov") }}' AS SSAP_NGUID,

    -- 2. External Federation & Conflation Lineage Identifiers
    c.county_id AS CountyLocalID,
    c.gers_id AS GERS_ID,
    c.conflation_status AS ConflationStatus,
    CASE c.conflation_status
        WHEN 'CONFLATED' THEN 'FRESNO_COUNTY_GIS_OVERTURE_CONFLATED'
        WHEN 'COUNTY_ONLY' THEN 'FRESNO_COUNTY_GIS'
        WHEN 'OVERTURE_ONLY' THEN 'OVERTURE_MAPS'
    END AS Source,

    -- 3. NENA-STA-010 Standardized Road Character Attributes (SSAP)
    upper(c.house_number) AS HNO,
    upper(c.house_number_suffix) AS HNS,
    upper(c.pre_directional) AS PRD,
    upper(c.street_name) AS STN,
    upper(c.street_type) AS STS,
    upper(c.post_directional) AS POD,
    upper(c.unit) AS Unit,

    -- 4. Jurisdictional, Municipal & Postal Attributes
    coalesce(m.muni, upper(c.community_name)) AS Muni,
    upper(c.community_name) AS CommunityName,
    upper(c.county) AS County,
    upper(c.state) AS State,
    c.postcode AS PostCode,
    upper(c.country) AS Country,

    -- 5. Automated Emergency Service Boundaries & PSAP Dispatch Attribution
    p.psap_name AS PSAP,
    p.psap_nguid AS PSAP_NGUID,
    p.psap_phone AS PSAP_Phone,
    f.esb_fire AS ESB_Fire,
    f.esb_fire_nguid AS ESB_Fire_NGUID,

    -- 6. Landmark & POI Dispatch Aliasing
    l.landmark_name AS LandmarkName,
    l.landmark_category AS LandmarkCategory,
    l.landmark_distance_meters AS LandmarkDistanceMeters,

    -- 7. Explicit Geospatial Coordinates for Dispatch Telematics
    c.longitude AS Longitude,
    c.latitude AS Latitude,

    -- 8. Spatial Discrepancy & Routing Quality Indicators
    c.spatial_offset_meters AS SpatialOffsetMeters,
    current_timestamp AS DateUpdate,

    -- 9. Native Geometry (Point / WKB)
    c.geom AS ST_Geometry

FROM conflated_data c
LEFT JOIN addr_psap p ON c.addr_uid = p.addr_uid AND p.rn = 1
LEFT JOIN addr_fire f ON c.addr_uid = f.addr_uid AND f.rn = 1
LEFT JOIN addr_muni m ON c.addr_uid = m.addr_uid AND m.rn = 1
LEFT JOIN landmarks l ON c.addr_uid = l.addr_uid
