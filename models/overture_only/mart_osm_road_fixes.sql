{{ config(materialized='table') }}

-- Open-data lineage: county centerline segments that OpenStreetMap (which Overture's roads come from)
-- is missing or names differently, each with a link to fix it in the OSM editor. Fixes made in OSM flow
-- into Overture's next release. The county's centerlines are CC0 (OpenAddresses license), so they can
-- be used as the source for these edits.
-- ponytail: one probe point per segment (see oo_road_overlap); a segment only partly mapped in OSM
-- counts as present.
SELECT
    '{{ county("label") }}' AS Jurisdiction,
    o.RCL_NGUID,
    o.St_Name AS CountyStreetName,
    round(o.length_m, 1) AS LengthM,
    CASE WHEN NOT o.overture_has_road THEN 'MISSING_IN_OSM' ELSE 'NAME_DIFFERS' END AS Issue,
    o.nearest_name AS OsmName,
    coalesce({{ osm_edit_url('o.nearest_osm_record_id') }},
             'https://www.openstreetmap.org/edit#map=19/' || round(o.probe_lat, 6) || '/' || round(o.probe_lon, 6)) AS OsmEditUrl,
    r.ST_Geometry
FROM {{ ref('oo_road_overlap') }} o
JOIN {{ ref('mart_ng911_road_centerlines') }} r USING (RCL_NGUID)
WHERE NOT o.overture_has_road OR NOT o.overture_name_agrees
