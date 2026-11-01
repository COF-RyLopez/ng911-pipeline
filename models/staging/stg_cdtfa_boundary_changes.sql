{{ config(materialized='view') }}

-- CDTFA's filed city/county boundary changes (Gov. Code 54900): annexations, detachments, corrections.
-- Attributes kept whole as props_json; the schema isn't documented.
-- BOE_CityCounty is the service's base layer of whole city / county polygons (e.g. all of unincorporated
-- Fresno County), not change areas; counting it made every disagreement look like a filed change.
SELECT layer_name, props_json, ST_MakeValid(geom) AS geom
FROM read_parquet('data/cache/cdtfa_boundary_changes.parquet')
WHERE geom IS NOT NULL
  AND layer_name NOT ILIKE '%CityCounty%'
