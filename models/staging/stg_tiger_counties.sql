{{ config(materialized='view') }}

-- US Census TIGER county polygons (TIGERweb), fetched for every registered county by fetch_tiger_counties().
SELECT CAST(GEOID AS VARCHAR) AS geoid, NAME AS name, ST_MakeValid(geom) AS geom
FROM read_parquet('data/cache/tiger_counties.parquet')
WHERE geom IS NOT NULL
