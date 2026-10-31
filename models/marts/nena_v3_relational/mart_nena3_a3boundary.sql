{{ config(materialized='table') }}

-- NENA v3.0 Relational Data Model: ng911.A3Boundary (incorporated municipality)
-- ponytail: Fresno city limits only; add Kings/Tulare city limits layers to extend.
SELECT
    row_number() OVER () AS ID,
    b.geom AS GEOMETRY,
    1 AS DiscrpAg_ID,
    coalesce(d.last_published, current_date) AS DateUpdate,
    'urn:emergency:uid:gis:A3:' || b.agency_code || ':{{ var("agency_domain", "fresnocountyca.gov") }}' AS NGUID,
    'US' AS Country,
    'CA' AS A1,
    'FRESNO' AS A2,
    b.agency_name AS A3
FROM {{ ref('stg_county_boundaries') }} b
LEFT JOIN {{ ref('stg_source_dates') }} d ON d.source = 'Fresno city limits'
WHERE b.agency_type = 'MUNICIPAL'
