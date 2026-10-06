{{ config(materialized='view') }}

WITH raw_county AS (
    SELECT *
    FROM read_parquet('data/cache/county_addresses.parquet')
)

SELECT
    county_id,
    upper(trim(house_number)) AS house_number,
    nullif(upper(trim(house_number_suffix)), '') AS house_number_suffix,
    {{ normalize_direction('pre_directional') }} AS pre_directional,
    upper(trim(street_name)) AS street_name,
    {{ normalize_street_type('street_type') }} AS street_type,
    {{ normalize_direction('post_directional') }} AS post_directional,
    nullif(upper(trim(unit)), '') AS unit,
    coalesce(upper(trim(community_name)), 'FRESNO') AS community_name,
    nullif(trim(postcode), '') AS postcode,
    'FRESNO' AS county,
    'CA' AS state,
    'US' AS country,
    longitude,
    latitude,
    ST_Point(longitude, latitude) AS geom,
    coalesce(source_agency, 'County of Fresno') AS source_agency
FROM raw_county
WHERE house_number IS NOT NULL 
  AND street_name IS NOT NULL
  AND longitude IS NOT NULL 
  AND latitude IS NOT NULL
