{{ config(materialized='table') }}

-- How much of the county's own centerline network the Overture (OpenStreetMap-derived, ODbL) roads
-- also contain: a measure of how far the open road map mirrors public-sector data. Comparison only;
-- nothing from Overture flows into the county marts.
-- ponytail: one probe point per county segment (ST_PointOnSurface) within ~15 m; sample along the
-- line if partial overlaps need measuring.
WITH probe AS (
    SELECT RCL_NGUID, St_Name,
           ST_Length(ST_Geometry) * 111320.0 AS length_m,
           ST_PointOnSurface(ST_GeomFromWKB(ST_AsWKB(ST_Geometry))) AS pt
    FROM {{ ref('mart_ng911_road_centerlines') }}
),
hits AS (
    SELECT p.RCL_NGUID, bool_or(instr(o.road_name, p.St_Name) > 0) AS name_agrees
    FROM probe p
    JOIN {{ ref('oo_road_centerlines') }} o ON ST_DWithin(p.pt, o.geom, 0.00015)
    GROUP BY 1
)
SELECT p.RCL_NGUID, p.St_Name, p.length_m,
       h.RCL_NGUID IS NOT NULL AS overture_has_road,
       coalesce(h.name_agrees, FALSE) AS overture_name_agrees
FROM probe p
LEFT JOIN hits h USING (RCL_NGUID)
