{{ config(
    materialized='table'
) }}

-- NENA v3.0 Relational Data Model: ng911.StSeg (Street Segment)
WITH rcl AS (
    SELECT *
    FROM {{ ref('mart_ng911_road_centerlines') }}
),

agencies AS (
    SELECT ID AS DiscrpAg_ID, DiscrpAgID
    FROM {{ ref('mart_nena3_discrpag') }}
),

st_names AS (
    SELECT 
        CompleteStNam_ID,
        St_PreDir,
        St_Name,
        St_Typ,
        St_PosDir
    FROM {{ ref('mart_nena3_completestnam') }}
)

SELECT
    row_number() OVER () AS ID,
    r.ST_Geometry AS GEOMETRY,
    coalesce(ag.DiscrpAg_ID, 1) AS DiscrpAg_ID,
    current_timestamp AS DateUpdate,
    r.RCL_NGUID AS NGUID,
    sn.CompleteStNam_ID,
    r.FromAddr_L,
    r.ToAddr_L,
    r.FromAddr_R,
    r.ToAddr_R,
    r.Parity_L,
    r.Parity_R,
    r.Country_L,
    r.Country_R,
    r.OneWay,
    r.SpeedLimit
FROM rcl r
LEFT JOIN agencies ag
  ON r.DisclID = ag.DiscrpAgID
LEFT JOIN st_names sn
  ON coalesce(r.St_PreDir, '') = coalesce(sn.St_PreDir, '')
 AND r.St_Name = sn.St_Name
 AND coalesce(r.St_Typ, '') = coalesce(sn.St_Typ, '')
 AND coalesce(r.St_PosDir, '') = coalesce(sn.St_PosDir, '')
