-- Mart: mart_esri_adm_siteaddresspoint
-- Model conforming authoritative NG911 address points to Esri Address Data Management (ADM) Solution schema
-- Compatible with ArcGIS Pro Address Data Management attribute rules (Split Intersecting Roads, Calculate Full Address)

{{ config(materialized='table') }}

WITH base AS (
    SELECT * FROM {{ ref('mart_ng911_county_remediation_export') }}
)

SELECT
    -- Esri ADM Primary Key
    SSAP_NGUID AS ADDRESSPTID,
    CountyLocalID AS LOCALID,
    'Site Address' AS POINTTYPE,

    -- Civic Address Components
    try_cast(HNO as integer) AS ADDRNUM,
    HNS AS HNSUF,
    PRD AS PREDIR,
    STN AS STNAME,
    STS AS STTYP,
    POD AS POSTDIR,
    trim(concat_ws(' ', PRD, STN, STS, POD)) AS FULLNAME,

    -- Sub-addressing
    Unit AS UNITID,
    CASE WHEN Unit IS NOT NULL THEN 'Unit' ELSE NULL END AS UNITTYPE,

    -- Full Address String (USPS / NENA Publication 28 sanitized)
    StandardizedAddress AS FULLADDR,

    -- Municipal and Postal Boundaries
    Muni AS MUNI,
    CommunityName AS COMMUNITY,
    PostCode AS ZIP,

    -- Esri ADM Status & Capture Method
    'Current' AS STATUS,
    CASE 
        WHEN OvertureBuildingGERS_ID IS NOT NULL THEN 'Structure Centroid'
        WHEN SpatialOffsetMeters > 50.0 THEN 'Long Driveway Access'
        ELSE 'Geocoded Offset'
    END AS CAPTUREMETH,

    -- NENA & Overture Cross-Reference Lineage
    OvertureAddressGERS_ID,
    OvertureBuildingGERS_ID AS STRUCTUREID,
    RoadCenterlineNGUID,
    SpatialOffsetMeters,
    IsExcessiveOffset,
    IsRangeViolation,
    RecommendedRemediationAction,
    PSAP,
    ESB_Fire,
    MapillaryGroundTruthURL,

    -- Point Geometry
    ST_Geometry AS geom
FROM base
