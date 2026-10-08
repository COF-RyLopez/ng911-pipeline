-- Mart: mart_esri_adm_roadcenterline
-- Model conforming authoritative NG911 road centerlines to Esri Address Data Management (ADM) Solution schema
-- Pre-sanitizes address ranges and street attributes for Arcade Attribute Rules (e.g., Split Intersecting Roads)

{{ config(materialized='table') }}

WITH rcl AS (
    SELECT * FROM {{ ref('mart_ng911_road_centerlines') }}
)

SELECT
    -- Esri ADM Centerline Identifiers
    RCL_NGUID AS CENTERLINEID,
    CountyLocalID AS LOCALID,
    FullStreetName AS FULLNAME,

    -- Parsed Road Name Components
    St_PreDir AS PREDIR,
    St_Name AS STNAME,
    St_Typ AS STTYP,
    St_PosDir AS POSTDIR,

    -- Numeric Address Ranges for Arcade Rule Compatibility (never null)
    coalesce(try_cast(FromAddr_L as integer), 0) AS FROMLEFT,
    coalesce(try_cast(ToAddr_L as integer), 0) AS TOLEFT,
    coalesce(try_cast(FromAddr_R as integer), 0) AS FROMRIGHT,
    coalesce(try_cast(ToAddr_R as integer), 0) AS TORIGHT,

    -- Left and Right Parity (O = Odd, E = Even, B = Both, Z = None)
    Parity_L AS PARITY_L,
    Parity_R AS PARITY_R,

    -- Road Classifications and Speeds
    RoadClass AS ROADCLASS,
    SpeedLimit AS SPEED,
    OneWay AS ONEWAY,

    -- Administrative Boundaries
    County_L AS COUNTY_L,
    County_R AS COUNTY_R,
    State_L AS STATE_L,
    State_R AS STATE_R,
    Country_L AS COUNTRY_L,
    Country_R AS COUNTRY_R,

    -- Operational Tracking
    AddressPointsCount,
    DateUpdate AS DATEUPDATE,

    -- Spatial Geometry
    ST_Geometry AS geom
FROM rcl
