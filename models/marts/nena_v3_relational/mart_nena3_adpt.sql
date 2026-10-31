{{ config(
    materialized='table'
) }}

-- NENA v3.0 Relational Data Model: ng911.AdPt (Site/Structure Address Point)
WITH regional_addresses AS (
    SELECT 
        *,
        TRY_CAST(regexp_extract(house_number, '^[0-9]+') AS INTEGER) AS num_int
    FROM {{ ref('stg_regional_addresses') }}
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
),

ad_numbers AS (
    SELECT 
        CompleteAdNum_ID,
        Add_Number,
        AddNum_Suf
    FROM {{ ref('mart_nena3_completeadnum') }}
)

SELECT
    row_number() OVER () AS ID,
    a.geom AS GEOMETRY,
    coalesce(ag.DiscrpAg_ID, 1) AS DiscrpAg_ID,
    -- ponytail: layer-level last edit; Fresno publishes DATE_MAINTAINED per record if finer dates are needed
    coalesce(d.last_published, current_date) AS DateUpdate,
    'urn:emergency:uid:gis:SSAP:' || a.county_id || ':' || a.agency_domain AS NGUID,
    sn.CompleteStNam_ID,
    an.CompleteAdNum_ID,
    ac.ID AS A1toA5Code_ID,
    a.community_name AS Post_Comm,
    a.postcode AS Post_Code,
    a.county AS County,
    a.state AS State,
    a.country AS Country,
    a.longitude AS Longitude,
    a.latitude AS Latitude
FROM regional_addresses a
LEFT JOIN agencies ag 
  ON a.agency_domain = ag.DiscrpAgID
LEFT JOIN st_names sn
  ON coalesce(a.pre_directional, '') = coalesce(sn.St_PreDir, '')
 AND a.street_name = sn.St_Name
 AND coalesce(a.street_type, '') = coalesce(sn.St_Typ, '')
 AND coalesce(a.post_directional, '') = coalesce(sn.St_PosDir, '')
LEFT JOIN ad_numbers an
  ON a.num_int = an.Add_Number
 AND coalesce(a.house_number_suffix, '') = coalesce(an.AddNum_Suf, '')
LEFT JOIN {{ ref('stg_source_dates') }} d
  ON lower(d.source) = lower(a.county) || ' addresses'
LEFT JOIN {{ ref('int_nena3_admin_areas') }} aa
  ON aa.feature = 'ADPT' AND aa.key = a.county_id || ':' || a.agency_domain
LEFT JOIN {{ ref('mart_nena3_a1toa5code') }} ac
  ON ac.A1 IS NOT DISTINCT FROM aa.A1 AND ac.A2 IS NOT DISTINCT FROM aa.A2 AND ac.A3 IS NOT DISTINCT FROM aa.A3
