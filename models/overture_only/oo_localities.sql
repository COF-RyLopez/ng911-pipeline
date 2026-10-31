{{ config(materialized='table') }}

-- Product 1: incorporated cities / places inside the county (NENA A3) from Overture divisions.
SELECT d.division_area_id, d.name, ST_GeomFromWKB(ST_AsWKB(d.geom)) AS geom
FROM read_parquet('data/cache/overture_divisions.parquet') d
CROSS JOIN {{ ref('oo_county_boundary') }} c
WHERE d.subtype = 'locality'
  AND ST_Within(ST_PointOnSurface(ST_GeomFromWKB(ST_AsWKB(d.geom))), c.geom)
