{{ config(
    materialized='table'
) }}

WITH addrs AS (
    SELECT 
        SSAP_NGUID,
        DisclID,
        HNO,
        TRY_CAST(regexp_extract(HNO, '^[0-9]+') AS INTEGER) AS addr_num,
        STN,
        ST_Geometry AS addr_geom
    FROM {{ ref('mart_ng911_addresses') }}
    WHERE HNO IS NOT NULL
),

roads AS (
    SELECT 
        RCL_NGUID,
        St_Name,
        FullStreetName,
        FromAddr_L,
        ToAddr_L,
        FromAddr_R,
        ToAddr_R,
        ST_Geometry AS road_geom
    FROM {{ ref('mart_ng911_road_centerlines') }}
),

-- Spatial join matching address points to road centerlines sharing the same street name within ~200m
candidate_connections AS (
    SELECT 
        a.SSAP_NGUID,
        a.DisclID,
        r.RCL_NGUID,
        a.HNO,
        a.addr_num,
        a.STN,
        r.FromAddr_L,
        r.ToAddr_L,
        r.FromAddr_R,
        r.ToAddr_R,
        round(ST_Distance(a.addr_geom, r.road_geom) * 111320.0, 2) AS distance_meters,
        ST_MakeLine(a.addr_geom, ST_ClosestPoint(r.road_geom, a.addr_geom)) AS fishbone_geom,
        ROW_NUMBER() OVER (
            PARTITION BY a.SSAP_NGUID 
            ORDER BY ST_Distance(a.addr_geom, r.road_geom) ASC
        ) AS rn
    FROM addrs a
    INNER JOIN roads r
        ON (
            a.STN = r.FullStreetName 
            OR a.STN = r.St_Name 
            OR instr(r.FullStreetName, a.STN) > 0 
            OR (length(r.St_Name) > 3 AND instr(a.STN, r.St_Name) > 0)
        )
       AND ST_DWithin(a.addr_geom, r.road_geom, 0.0020) -- ~200m corridor
),

best_connections AS (
    SELECT *
    FROM candidate_connections
    WHERE rn = 1
)

SELECT
    'urn:emergency:uid:gis:FISHBONE:' || row_number() OVER () || ':{{ var("agency_domain", "fresnocountyca.gov") }}' AS FishboneID,
    DisclID,
    SSAP_NGUID,
    RCL_NGUID,
    HNO,
    STN,
    distance_meters AS DistanceMeters,
    
    -- NENA QA/QC Assertion: Flags points sitting > 50m from road centerline
    CASE WHEN distance_meters > 50.0 THEN TRUE ELSE FALSE END AS IsExcessiveOffset,
    
    -- NENA QA/QC Assertion: Flags house numbers outside synthesized address ranges
    CASE 
        WHEN (FromAddr_L IS NOT NULL AND (addr_num < FromAddr_L OR addr_num > ToAddr_L))
         AND (FromAddr_R IS NOT NULL AND (addr_num < FromAddr_R OR addr_num > ToAddr_R)) 
        THEN TRUE 
        ELSE FALSE 
    END AS IsRangeViolation,

    -- Vector Line connecting the address point to the road centerline
    fishbone_geom AS ST_Geometry,
    current_timestamp AS DateUpdate

FROM best_connections
