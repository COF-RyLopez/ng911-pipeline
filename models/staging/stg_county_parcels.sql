{{ config(materialized='view') }}

-- County tax parcels (Fresno REGIONAL_PARCELS_VW, fetched by scripts/fetch_county_parcels.py).
SELECT parcel_id, apn, ST_MakeValid(geom) AS geom
FROM read_parquet('data/cache/county_parcels.parquet')
WHERE geom IS NOT NULL
