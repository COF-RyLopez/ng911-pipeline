{{ config(materialized='table') }}

-- Product 2: the county's polygon from each source. CDTFA (the state's tax boundary, seamless statewide)
-- is the frame the others are compared against: Overture divisions (OpenStreetMap-derived) and US Census TIGER.
SELECT 'CDTFA' AS source, ST_MakeValid(ST_Union_Agg(geom)) AS geom
FROM {{ ref('stg_cdtfa_boundaries') }}
WHERE kind = 'COUNTY' AND county = '{{ county("name") }}'
UNION ALL
SELECT 'OVERTURE', ST_MakeValid(geom) FROM {{ ref('oo_county_boundary') }}
UNION ALL
SELECT 'TIGER', ST_MakeValid(ST_Union_Agg(geom))
FROM {{ ref('stg_tiger_counties') }}
WHERE geoid = '{{ var("county") }}'
