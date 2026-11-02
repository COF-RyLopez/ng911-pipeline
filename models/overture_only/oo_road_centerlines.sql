{{ config(materialized='table') }}
{%- set sfx = street_type_suffix_regex() %}
{%- set name = "regexp_replace(upper(trim(t.road_name)), '[.]+$', '')" %}

-- Product 1: named Overture road segments touching the county (the RCL layer).
-- License: Overture transportation is derived from OpenStreetMap and is ODbL; keep it out of county deliverables.
-- The name is parsed into NENA parts the same way as Overture addresses ('NORTH BLACKSTONE AVENUE' -> N / BLACKSTONE / AVE).
SELECT t.overture_segment_id, t.road_name, t.road_class, t.osm_record_id,
       {{ normalize_direction("nullif(regexp_extract(regexp_replace(" ~ name ~ ", '" ~ sfx ~ "', ''), '^(N|S|E|W|NE|NW|SE|SW|NORTH|SOUTH|EAST|WEST) +', 1), '')") }} AS st_predir,
       nullif(trim(regexp_replace(regexp_replace({{ name }}, '{{ sfx }}', ''), '^(N|S|E|W|NE|NW|SE|SW|NORTH|SOUTH|EAST|WEST) +', '')), '') AS st_name,
       {{ normalize_street_type("nullif(regexp_extract(" ~ name ~ ", '" ~ sfx ~ "', 1), '')") }} AS st_posttyp,
       {{ osm_edit_url('t.osm_record_id') }} AS osm_edit_url,
       ST_GeomFromWKB(ST_AsWKB(t.geom)) AS geom
FROM {{ ref('stg_overture_transportation') }} t
CROSS JOIN {{ ref('oo_county_boundary') }} c
WHERE t.road_subtype = 'road'
  AND coalesce(t.road_class, '') NOT IN ('footway', 'sidewalk', 'crosswalk', 'path', 'pedestrian', 'steps', 'cycleway', 'bridleway')
  AND ST_Intersects(ST_GeomFromWKB(ST_AsWKB(t.geom)), c.geom)
