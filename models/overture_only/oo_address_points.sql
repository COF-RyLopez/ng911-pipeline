{{ config(materialized='table') }}

-- Product 1: Overture address points inside the county (the SSAP layer an open-data-only build gets).
SELECT a.overture_id, a.house_number, a.pre_directional, a.street_name, a.street_type,
       a.community_name, a.postcode, ST_GeomFromWKB(ST_AsWKB(a.geom)) AS geom
FROM {{ ref('stg_overture_addresses') }} a
CROSS JOIN {{ ref('oo_county_boundary') }} c
WHERE a.street_name IS NOT NULL  -- STN is mandatory; see the remediation export
  AND ST_Within(ST_GeomFromWKB(ST_AsWKB(a.geom)), c.geom)
