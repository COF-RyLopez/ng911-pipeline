{{ config(materialized='table') }}

-- Product 1 (Overture-only NG911): the county polygon from Overture divisions. Every other oo_ model
-- is clipped to it, so this build needs no county data source at all.
SELECT
    division_area_id,
    division_id,
    name,
    osm_record_id,  -- lineage: the OpenStreetMap relation for the county
    ST_GeomFromWKB(ST_AsWKB(geom)) AS geom  -- drop the CRS84 tag so joins with untagged geometries match
FROM read_parquet('data/cache/overture_divisions.parquet')
WHERE subtype = 'county'
  AND upper(name) IN ('{{ county("name") }} COUNTY', '{{ county("name") }}')
-- a coastal county can have land and maritime areas; prefer the land one
ORDER BY (class = 'land') DESC NULLS LAST
LIMIT 1
