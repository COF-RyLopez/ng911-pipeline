{{ config(materialized='table') }}

-- Topology QA for the law enforcement dispatch layer (City_County_CAD).
WITH raw AS (
    SELECT OBJECTID, upper(trim(NAME)) AS name, ST_GeomFromWKB(ST_AsWKB(geom)) AS geom
    FROM read_parquet('data/cache/county_cad_psap.parquet')
    WHERE geom IS NOT NULL
),
p AS (SELECT *, ST_MakeValid(geom) AS g FROM raw),
pairs AS (
    SELECT a.OBJECTID AS id_a, a.name AS name_a, b.OBJECTID AS id_b, b.name AS name_b,
           ST_Intersection(a.g, b.g) AS ix
    FROM p a JOIN p b ON a.OBJECTID < b.OBJECTID AND ST_Intersects(a.g, b.g)
),
sized AS (
    SELECT *, ST_Area(ST_Transform(ix, 'EPSG:4326', 'EPSG:3310', always_xy := true)) / 1e4 AS ha FROM pairs
)
SELECT 'INVALID_GEOMETRY' AS IssueType, OBJECTID AS ObjectID_A, name AS Name_A,
       NULL::BIGINT AS ObjectID_B, NULL::VARCHAR AS Name_B, NULL::DOUBLE AS OverlapHectares,
       'Polygon is not valid; repaired with ST_MakeValid before point-in-polygon joins' AS Description,
       geom AS ST_Geometry
FROM raw WHERE NOT ST_IsValid(geom)
UNION ALL
SELECT CASE WHEN name_a = name_b THEN 'DUPLICATE_POLYGON' ELSE 'OVERLAP' END,
       id_a, name_a, id_b, name_b, round(ha, 2),
       CASE WHEN name_a = name_b THEN 'Two polygons for the same agency overlap; addresses here fall in both'
            ELSE 'Polygons for different agencies overlap; addresses here are dual-assigned' END,
       ix
FROM sized WHERE ha > 0.1
