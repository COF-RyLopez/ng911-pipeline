{{ config(materialized='view') }}

-- Addresses of the county this run builds (var `county`); each county's source mapping lives in
-- stg_regional_addresses.
SELECT
    county_id,
    house_number,
    house_number_suffix,
    pre_directional,
    street_name,
    street_type,
    post_directional,
    unit,
    community_name,
    postcode,
    county,
    state,
    country,
    longitude,
    latitude,
    geom,
    source_agency,
    address_status
FROM {{ ref('stg_regional_addresses') }}
WHERE county = '{{ county("name") }}'
  AND longitude IS NOT NULL AND latitude IS NOT NULL
