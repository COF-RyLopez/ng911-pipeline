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
    coalesce(d.last_published, current_date) AS DateUpdate,
    r.RCL_NGUID AS NGUID,
    sn.CompleteStNam_ID,
    coalesce(als.AliasSet_ID, 0)::BIGINT AS AliasSet_ID,
    r.FromAddr_L,
    r.ToAddr_L,
    r.FromAddr_R,
    r.ToAddr_R,
    r.Parity_L,
    r.Parity_R,
    r.Country_L,
    r.Country_R,
    acl.ID AS A1toA5CodeL_ID,
    acr.ID AS A1toA5CodeR_ID,
    rc.ID AS RdClass_ID,
    r.OneWay,
    r.SpeedLimit
FROM rcl r
LEFT JOIN (SELECT DISTINCT street_segment_id, AliasSet_ID FROM {{ ref('int_alias_sets') }}) als
  ON r.CountyLocalID = als.street_segment_id
LEFT JOIN agencies ag
  ON r.DisclID = ag.DiscrpAgID
LEFT JOIN {{ ref('stg_source_dates') }} d
  ON lower(d.source) = lower(r.County_L) || ' centerlines'
LEFT JOIN {{ ref('int_nena3_admin_areas') }} al ON al.feature = 'STSEG_L' AND al.key = r.RCL_NGUID
LEFT JOIN {{ ref('int_nena3_admin_areas') }} ar ON ar.feature = 'STSEG_R' AND ar.key = r.RCL_NGUID
LEFT JOIN {{ ref('mart_nena3_a1toa5code') }} acl
  ON acl.A1 IS NOT DISTINCT FROM al.A1 AND acl.A2 IS NOT DISTINCT FROM al.A2 AND acl.A3 IS NOT DISTINCT FROM al.A3
LEFT JOIN {{ ref('mart_nena3_a1toa5code') }} acr
  ON acr.A1 IS NOT DISTINCT FROM ar.A1 AND acr.A2 IS NOT DISTINCT FROM ar.A2 AND acr.A3 IS NOT DISTINCT FROM ar.A3
LEFT JOIN {{ ref('mart_nena3_rdclass') }} rc
  ON rc.RdClass = CASE
      WHEN r.SourceClassification LIKE '%link' THEN 'Ramp'
      WHEN r.SourceClassification IN ('motorway', 'trunk') THEN 'Primary'
      WHEN r.SourceClassification IN ('primary', 'secondary') THEN 'Secondary'
      WHEN r.SourceClassification = 'service' THEN 'Service Drive'
      WHEN r.SourceClassification = 'track' THEN 'Vehicular Trail'
      ELSE 'Local'
  END
LEFT JOIN st_names sn
  ON coalesce(r.St_PreDir, '') = coalesce(sn.St_PreDir, '')
 AND r.St_Name = sn.St_Name
 AND coalesce(r.St_Typ, '') = coalesce(sn.St_Typ, '')
 AND coalesce(r.St_PosDir, '') = coalesce(sn.St_PosDir, '')
