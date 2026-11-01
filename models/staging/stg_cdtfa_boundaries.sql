{{ config(materialized='view') }}

-- CDTFA city and county boundaries from the CA state geoportal (California Department of Technology,
-- public domain), land-only versions. Fetched for every registered county by fetch_cdtfa_boundaries().
SELECT 'CITY' AS kind, upper(trim(CDT_NAME_SHORT)) AS name, regexp_replace(upper(trim(CDTFA_COUNTY)), ' COUNTY$', '') AS county,
       CAST(CENSUS_GEOID AS VARCHAR) AS census_geoid, ST_MakeValid(geom) AS geom
FROM read_parquet('data/cache/cdtfa_cities.parquet')
WHERE geom IS NOT NULL
UNION ALL
SELECT 'COUNTY', upper(trim(CDT_NAME_SHORT)), regexp_replace(upper(trim(CDTFA_COUNTY)), ' COUNTY$', ''),
       CAST(CENSUS_GEOID AS VARCHAR), ST_MakeValid(geom)
FROM read_parquet('data/cache/cdtfa_counties.parquet')
WHERE geom IS NOT NULL
