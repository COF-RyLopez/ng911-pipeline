{{ config(materialized='table') }}

-- Product 1: named Overture road segments touching the county (the RCL layer).
-- License: Overture transportation is derived from OpenStreetMap and is ODbL; keep it out of county deliverables.
SELECT t.overture_segment_id, t.road_name, t.road_class, t.osm_record_id,
       {{ osm_edit_url('t.osm_record_id') }} AS osm_edit_url,
       ST_GeomFromWKB(ST_AsWKB(t.geom)) AS geom
FROM {{ ref('stg_overture_transportation') }} t
CROSS JOIN {{ ref('oo_county_boundary') }} c
WHERE t.road_subtype = 'road'
  AND coalesce(t.road_class, '') NOT IN ('footway', 'sidewalk', 'crosswalk', 'path', 'pedestrian', 'steps', 'cycleway', 'bridleway')
  AND ST_Intersects(ST_GeomFromWKB(ST_AsWKB(t.geom)), c.geom)
