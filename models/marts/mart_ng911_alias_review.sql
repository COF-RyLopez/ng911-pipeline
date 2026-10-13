{{ config(materialized='table') }}

-- Road geometries carrying more than one street name, for county GIS review.
--   UNRESOLVED     neither address points nor published ranges identified the primary name
--   NAME_CONFLICT  the names share a base name but differ in type/direction (likely a data error,
--                  e.g. NORTH SHIRK ROAD / NORTH SHIRK STREET)
--   ALIAS          a genuine alias (e.g. HIGHWAY 43 / 8TH AVE)
SELECT
    p.county_name AS County,
    p.street_segment_id AS CountyLocalID,
    p.full_street_name AS PrimaryName,
    p.alias_names AS AliasNames,
    p.primary_name_method AS PrimaryNameMethod,
    CASE
        WHEN EXISTS (SELECT 1 FROM {{ ref('int_street_aliases') }} a
                     WHERE a.street_segment_id = p.street_segment_id AND a.street_name = p.street_name) THEN 'NAME_CONFLICT'
        WHEN p.primary_name_method = 'UNRESOLVED' THEN 'UNRESOLVED'
        ELSE 'ALIAS'
    END AS ReviewCategory,
    p.geom AS ST_Geometry
FROM {{ ref('int_road_centerlines') }} p
WHERE p.primary_name_method IS NOT NULL
