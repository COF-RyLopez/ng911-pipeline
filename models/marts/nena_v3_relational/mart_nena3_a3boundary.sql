{{ config(materialized='table') }}

-- NENA v3.0 Relational Data Model: ng911.A3Boundary (incorporated municipality), one row per city.
-- ponytail: city limits come from the county's boundary layers (Fresno only so far); other counties get no rows.
SELECT
    row_number() OVER (ORDER BY b.agency_code) AS ID,
    b.geom AS GEOMETRY,
    1 AS DiscrpAg_ID,
    coalesce(d.last_published, current_date) AS DateUpdate,
    'urn:emergency:uid:gis:A3:' || b.agency_code || ':{{ county("agency_domain") }}' AS NGUID,
    'US' AS Country,
    'CA' AS A1,
    '{{ county("name") }}' AS A2,
    b.agency_name AS A3
FROM (
    SELECT agency_code, agency_name, ST_Union_Agg(geom) AS geom
    FROM {{ ref('stg_county_boundaries') }}
    WHERE agency_type = 'MUNICIPAL'
      AND agency_name <> 'COUNTY OF {{ county("name") }}'  -- the layer's unincorporated remainder is not a city
    GROUP BY 1, 2
) b
LEFT JOIN {{ ref('stg_source_dates') }} d ON d.source = 'Fresno city limits'
