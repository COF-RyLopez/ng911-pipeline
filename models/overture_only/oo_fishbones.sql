{{ config(materialized='table') }}

-- Product 1: each Overture address linked to the nearest Overture road carrying its street name,
-- within the same ~400 m corridor the county build uses (mart_ng911_qa_fishbones).
SELECT overture_id, overture_segment_id, distance_meters, distance_meters > 50.0 AS is_excessive_offset
FROM (
    SELECT a.overture_id, r.overture_segment_id,
           round(ST_Distance(a.geom, r.geom) * 111320.0, 2) AS distance_meters,
           row_number() OVER (PARTITION BY a.overture_id ORDER BY ST_Distance(a.geom, r.geom)) AS rn
    FROM {{ ref('oo_address_points') }} a
    JOIN {{ ref('oo_road_centerlines') }} r
      ON length(a.street_name) > 0
     AND instr(r.road_name, a.street_name) > 0
     AND ST_DWithin(a.geom, r.geom, 0.0040)
)
WHERE rn = 1
