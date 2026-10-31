{{ config(materialized='table') }}

-- Product 1: each Overture address linked to the nearest Overture road carrying its street name,
-- within the same ~400 m corridor the county build uses (mart_ng911_qa_fishbones).
WITH a AS (
    SELECT overture_id, geom, {{ street_match_key('street_name') }} AS name_key
    FROM {{ ref('oo_address_points') }}
    WHERE length(street_name) > 0
),
r AS (
    SELECT overture_segment_id, geom, {{ street_match_key('road_name') }} AS name_key
    FROM {{ ref('oo_road_centerlines') }}
)
SELECT overture_id, overture_segment_id, distance_meters, distance_meters > 50.0 AS is_excessive_offset
FROM (
    SELECT a.overture_id, r.overture_segment_id,
           round(ST_Distance(a.geom, r.geom) * 111320.0, 2) AS distance_meters,
           row_number() OVER (PARTITION BY a.overture_id ORDER BY ST_Distance(a.geom, r.geom)) AS rn
    FROM a
    -- whole-word match on space-padded keys: "E" doesn't match every road with an E in it,
    -- and "N EIGHTH" (county address) matches "NORTH 8TH STREET" (OSM road)
    JOIN r ON instr(r.name_key, a.name_key) > 0
          AND ST_DWithin(a.geom, r.geom, 0.0040)
)
WHERE rn = 1
