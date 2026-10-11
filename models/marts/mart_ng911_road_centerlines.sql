{{ config(
    materialized='table'
) }}

WITH county_streets AS (
    SELECT * FROM {{ ref('stg_county_streets') }}
),

county_addresses AS (
    SELECT
        county_id,
        TRY_CAST(regexp_extract(house_number, '^[0-9]+') AS INTEGER) AS addr_num,
        street_name,
        street_type,
        geom
    FROM {{ ref('stg_county_addresses') }}
    WHERE house_number IS NOT NULL
),

-- Spatial projection: Match county address points to their closest centerline segment
addr_street_matches AS (
    SELECT
        s.street_segment_id,
        a.addr_num,
        ROW_NUMBER() OVER (
            PARTITION BY a.county_id 
            ORDER BY ST_Distance(a.geom, s.geom) ASC
        ) AS rn
    FROM county_streets s
    INNER JOIN county_addresses a
        ON s.street_name = a.street_name
       AND ST_DWithin(a.geom, s.geom, {{ var('conflation_distance_degrees', 0.00015) }} * 3) -- ~45m corridor
),

-- Calculate Left (Even) and Right (Odd) address ranges per segment
address_ranges AS (
    SELECT
        street_segment_id,
        count(addr_num) AS mapped_address_count,
        min(CASE WHEN addr_num % 2 = 0 THEN addr_num END) AS from_addr_l,
        max(CASE WHEN addr_num % 2 = 0 THEN addr_num END) AS to_addr_l,
        min(CASE WHEN addr_num % 2 = 1 THEN addr_num END) AS from_addr_r,
        max(CASE WHEN addr_num % 2 = 1 THEN addr_num END) AS to_addr_r
    FROM addr_street_matches
    WHERE rn = 1
    GROUP BY street_segment_id
)

SELECT
    -- 1. NENA Mandatory Agency and Globally Unique Identifiers
    '{{ var("agency_domain", "fresnocountyca.gov") }}' AS DisclID,
    'urn:emergency:uid:gis:RCL:' || s.street_segment_id || ':{{ var("agency_domain", "fresnocountyca.gov") }}' AS RCL_NGUID,
    s.street_segment_id AS CountyLocalID,

    -- 2. NENA-STA-010 Standardized Road Name Elements
    s.pre_directional AS St_PreDir,
    s.street_name AS St_Name,
    s.street_type AS St_Typ,
    s.post_directional AS St_PosDir,
    s.full_street_name AS FullStreetName,

    -- 3. NENA Address Ranges & Parity: county-published ranges when present, else synthesized from address points
    rg.FromAddr_L,
    rg.ToAddr_L,
    rg.FromAddr_R,
    rg.ToAddr_R,
    {{ parity('rg.FromAddr_L', 'rg.ToAddr_L') }} AS Parity_L,
    {{ parity('rg.FromAddr_R', 'rg.ToAddr_R') }} AS Parity_R,
    rg.RangeSource,
    coalesce(r.mapped_address_count, 0) AS AddressPointsCount,

    -- 4. Jurisdictional Attribution
    s.county_name AS County_L,
    s.county_name AS County_R,
    'CA' AS State_L,
    'CA' AS State_R,
    'US' AS Country_L,
    'US' AS Country_R,

    -- 5. Operational Dispatch Attributes
    coalesce(s.speed_mph, CASE upper(s.road_class)
        WHEN 'EXPRESSWAY' THEN 65
        WHEN 'ARTERIAL' THEN 45
        WHEN 'COLLECTOR' THEN 35
        ELSE 25
    END) AS SpeedLimit,
    coalesce(s.one_way, 'B') AS OneWay, -- published one-way where available, else both directions
    s.road_class AS RoadClass,

    -- 6. 100% Authoritative County Geometry (Zero ODbL / OSM Licensing Contamination)
    s.geom AS ST_Geometry,
    current_timestamp AS DateUpdate

FROM county_streets s
LEFT JOIN address_ranges r ON s.street_segment_id = r.street_segment_id
CROSS JOIN LATERAL (
    SELECT
        CASE WHEN s.has_published_ranges THEN 'Published' ELSE 'Synthesized' END AS RangeSource,
        CASE WHEN s.has_published_ranges THEN s.pub_from_addr_l ELSE r.from_addr_l END AS FromAddr_L,
        CASE WHEN s.has_published_ranges THEN s.pub_to_addr_l ELSE r.to_addr_l END AS ToAddr_L,
        CASE WHEN s.has_published_ranges THEN s.pub_from_addr_r ELSE r.from_addr_r END AS FromAddr_R,
        CASE WHEN s.has_published_ranges THEN s.pub_to_addr_r ELSE r.to_addr_r END AS ToAddr_R
) rg
