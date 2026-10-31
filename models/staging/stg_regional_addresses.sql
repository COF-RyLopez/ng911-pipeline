{{ config(materialized='view') }}

-- One CTE per county: that county's address source mapped to the shared columns (the county adapter).
-- stg_county_addresses picks the county this run builds; this model keeps every county for the
-- regional NENA AdPt table.
WITH fresno AS (
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
        CASE
            WHEN source_agency = 'City of Fresno' THEN 'fresno.gov'
            WHEN source_agency = 'City of Clovis' THEN 'cityofclovis.com'
            ELSE 'fresnocountyca.gov'
        END AS agency_domain,
        coalesce(source_agency, 'County of Fresno') AS source_agency,
        coalesce(nullif(upper(trim(address_status)), ''), 'ACTIVE') AS address_status
    FROM read_parquet('data/cache/county_addresses.parquet')
    WHERE house_number IS NOT NULL AND street_name IS NOT NULL
      AND longitude IS NOT NULL AND latitude IS NOT NULL
),

kings AS (
    SELECT 
        county_id,
        upper(trim(house_number)) AS house_number,
        NULL::VARCHAR AS house_number_suffix,
        {{ normalize_direction('pre_directional') }} AS pre_directional,
        upper(trim(street_name)) AS street_name,
        {{ normalize_street_type('street_type') }} AS street_type,
        NULL::VARCHAR AS post_directional,
        NULL::VARCHAR AS unit,
        coalesce(upper(trim(community_name)), 'KINGS') AS community_name,
        nullif(trim(postcode), '') AS postcode,
        'KINGS' AS county,
        'CA' AS state,
        'US' AS country,
        longitude,
        latitude,
        ST_Point(longitude, latitude) AS geom,
        'countyofkings.com' AS agency_domain,
        'County of Kings' AS source_agency,
        'ACTIVE' AS address_status
    FROM read_parquet('data/cache/kings_addresses.parquet')
    WHERE house_number IS NOT NULL AND street_name IS NOT NULL
),

tulare AS (
    SELECT 
        county_id,
        upper(trim(house_number)) AS house_number,
        nullif(upper(trim(house_number_suffix)), '') AS house_number_suffix,
        {{ normalize_direction('pre_directional') }} AS pre_directional,
        upper(trim(street_name)) AS street_name,
        {{ normalize_street_type('street_type') }} AS street_type,
        NULL::VARCHAR AS post_directional,
        NULL::VARCHAR AS unit,
        coalesce(upper(trim(community_name)), 'TULARE') AS community_name,
        nullif(trim(postcode), '') AS postcode,
        'TULARE' AS county,
        'CA' AS state,
        'US' AS country,
        longitude,
        latitude,
        ST_Point(longitude, latitude) AS geom,
        'tularecounty.ca.gov' AS agency_domain,
        'County of Tulare' AS source_agency,
        'ACTIVE' AS address_status
    FROM read_parquet('data/cache/tulare_addresses.parquet')
    WHERE house_number IS NOT NULL AND street_name IS NOT NULL
)

SELECT * FROM fresno
UNION ALL
SELECT * FROM kings
UNION ALL
SELECT * FROM tulare
