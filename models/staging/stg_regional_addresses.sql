{{ config(materialized='view') }}

WITH fresno AS (
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
        'FRESNO' AS county,
        'CA' AS state,
        'US' AS country,
        longitude,
        latitude,
        geom,
        CASE 
            WHEN source_agency = 'City of Fresno' THEN 'fresno.gov'
            WHEN source_agency = 'City of Clovis' THEN 'cityofclovis.com'
            ELSE 'fresnocountyca.gov'
        END AS agency_domain,
        source_agency,
        address_status
    FROM {{ ref('stg_county_addresses') }}
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
