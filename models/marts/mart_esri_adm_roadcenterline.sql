-- Mart: mart_esri_adm_roadcenterline
-- Esri Address Data Management (ADM 2.5, Mar 2026) RoadCenterline: exactly the solution's non-system
-- fields, in its order, with values limited to its coded-value domains (tested in schema.yml).
-- Schema read from the ADM ArcGIS Pro project's "Address Data Management.gdb".
-- ponytail: munileft/right, zipleft/right, esn/msag, route and grade fields are NULL; add a
-- spatial join to city limits / ZIP polygons when ADM needs them populated.

{{ config(materialized='table') }}

SELECT
    CountyLocalID AS centerlineid,
    RCL_NGUID AS rclnguid,
    '{{ var("agency_domain", "fresnocountyca.gov") }}' AS discrpagid,
    NULL::VARCHAR AS rangeprefixleft,
    -- 0-0 is how ADM stores "no range" (AddressParity domain: Z = Address Range 0-0)
    coalesce(try_cast(FromAddr_L AS INTEGER), 0) AS fromleft,
    coalesce(try_cast(ToAddr_L AS INTEGER), 0) AS toleft,
    Parity_L AS parityleft,
    NULL::VARCHAR AS rangeprefixright,
    coalesce(try_cast(FromAddr_R AS INTEGER), 0) AS fromright,
    coalesce(try_cast(ToAddr_R AS INTEGER), 0) AS toright,
    Parity_R AS parityright,
    FullStreetName AS fullname,
    NULL::VARCHAR AS fedroute,
    NULL::VARCHAR AS fedrtetype,
    NULL::VARCHAR AS afedrte,
    NULL::VARCHAR AS afedrtetype,
    NULL::VARCHAR AS stroute,
    NULL::VARCHAR AS strtetype,
    NULL::VARCHAR AS astrte,
    NULL::VARCHAR AS astrtetype,
    NULL::VARCHAR AS ctyroute,
    CASE OneWay WHEN 'FT' THEN 'From-To' WHEN 'TF' THEN 'To-From' WHEN 'B' THEN 'Both' ELSE 'Unknown' END AS onewaydir,
    NULL::INTEGER AS roadlevel,
    NULL::VARCHAR AS inwater,
    -- stg_county_streets classes -> ADM RoadClass domain
    CASE RoadClass
        WHEN 'Freeway' THEN 'Freeway'
        WHEN 'Expressway' THEN 'Highway'
        WHEN 'Super Arterial' THEN 'Major Arterial'
        WHEN 'Arterial' THEN 'Minor Arterial'
        WHEN 'Collector' THEN 'Collector'
        WHEN 'Local' THEN 'Local'
        WHEN 'Private' THEN 'Service'
        ELSE 'Unknown'
    END AS roadclass,
    Country_L AS countryleft,
    Country_R AS countryright,
    State_L AS stateleft,
    State_R AS stateright,
    County_L AS countyleft,
    County_R AS countyright,
    NULL::VARCHAR AS munileft,
    NULL::VARCHAR AS muniright,
    NULL::VARCHAR AS zipleft,
    NULL::VARCHAR AS zipright,
    NULL::VARCHAR AS msagleft,
    NULL::VARCHAR AS msagright,
    NULL::VARCHAR AS esnleft,
    NULL::VARCHAR AS esnright,
    NULL::VARCHAR AS precenterlineid,
    ST_Geometry AS geom
FROM {{ ref('mart_ng911_road_centerlines') }}
