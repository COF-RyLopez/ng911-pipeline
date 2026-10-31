-- Mart: mart_esri_adm_siteaddresspoint
-- Esri Address Data Management (ADM 2.5, Mar 2026) SiteAddressPoint: exactly the solution's non-system
-- fields, in its order, with values limited to its coded-value domains (tested in schema.yml).
-- Schema read from the ADM ArcGIS Pro project's "Address Data Management.gdb".
-- ponytail: ADM fields with no source here (alternate units, esn, msag, usngcoord, placename) are NULL;
-- addressptid stays NULL until the pipeline builds ADM AddressPoint features.

{{ config(materialized='table') }}

WITH base AS (
    SELECT r.*, a.County, a.State, a.Country
    FROM {{ ref('mart_ng911_county_remediation_export') }} r
    LEFT JOIN {{ ref('mart_ng911_addresses') }} a USING (SSAP_NGUID)
),

parts AS (
    SELECT
        *,
        nullif(trim(Unit), '') AS unit_clean,
        nullif(trim(concat_ws(' ', PRD, STN, STS, POD)), '') AS road_fullname
    FROM base
)

SELECT
    CountyLocalID AS siteaddid,
    NULL::VARCHAR AS addressptid,
    SSAP_NGUID AS sitenguid,
    '{{ county("agency_domain") }}' AS discrpagid,
    NULL::VARCHAR AS preaddrnum,
    nullif(trim(HNS), '') AS addrnumsuf,
    trim(HNO::VARCHAR) AS addrnum,
    NULL::VARCHAR AS addrrange,
    CASE WHEN unit_clean IS NOT NULL THEN 'UNIT' END AS unittype,
    unit_clean AS unitid,
    NULL::VARCHAR AS altunittype,
    NULL::VARCHAR AS altunitid,
    NULL::VARCHAR AS secondaltunittype,
    NULL::VARCHAR AS secondaltunitid,
    NULL::VARCHAR AS thirdaltunittype,
    NULL::VARCHAR AS thirdaltunitid,
    NULL::VARCHAR AS fourthaltunittype,
    NULL::VARCHAR AS fourthaltunitid,
    road_fullname AS fullname,
    concat_ws(' ', trim(HNO::VARCHAR) || coalesce(nullif(trim(HNS), ''), ''), road_fullname,
              CASE WHEN unit_clean IS NOT NULL THEN 'UNIT ' || unit_clean END) AS fulladdr,
    NULL::VARCHAR AS placename,
    Country AS country,
    State AS stateabbreviation,
    County AS county,
    Muni AS municipality,
    NULL::VARCHAR AS esn,
    NULL::VARCHAR AS msag,
    NULL::VARCHAR AS usngcoord,
    -- SiteAddressLocation domain: structure points sit inside an Overture building footprint
    CASE WHEN OvertureBuildingGERS_ID IS NOT NULL THEN 'Building' ELSE 'Unknown' END AS pointtype,
    -- PointCollectionMethod domain has no value for "derived from county records"
    'Other' AS capturemeth,
    'Current' AS status,
    ST_Geometry AS geom
FROM parts
