{{ config(materialized='table') }}

-- Product 2: pair each CDTFA (state) city with the county's own city-limits polygon for it.
-- Paired by largest overlap, not by name, so county naming ("CITY OF CLOVIS", "CLOVIS") doesn't matter.
WITH st AS (
    SELECT name AS city, ST_MakeValid(ST_Union_Agg(geom)) AS geom
    FROM {{ ref('stg_cdtfa_boundaries') }}
    WHERE kind = 'CITY' AND county = '{{ county("name") }}'
    GROUP BY 1
),
lc AS (
    SELECT agency_name AS city, ST_MakeValid(ST_Union_Agg(geom)) AS geom
    FROM {{ ref('stg_county_boundaries') }}
    WHERE agency_type = 'MUNICIPAL'
    GROUP BY 1
),
pairs AS (
    SELECT s.city AS state_city, l.city AS local_city,
           {{ area_km2('ST_Intersection(s.geom, l.geom)') }} AS overlap_km2
    FROM st s
    JOIN lc l ON ST_Intersects(s.geom, l.geom)
),
-- a pair counts only when each side is the other's biggest overlap (a sliver touching a neighbour isn't a match)
matched AS (
    SELECT p.*
    FROM pairs p
    QUALIFY row_number() OVER (PARTITION BY state_city ORDER BY overlap_km2 DESC) = 1
        AND row_number() OVER (PARTITION BY local_city ORDER BY overlap_km2 DESC) = 1
)
SELECT s.city AS state_city, m.local_city, s.geom AS state_geom, l.geom AS local_geom,
       coalesce(m.overlap_km2, 0) AS overlap_km2
FROM st s
LEFT JOIN matched m ON m.state_city = s.city
LEFT JOIN lc l ON l.city = m.local_city
UNION ALL
SELECT NULL, l.city, NULL, l.geom, 0
FROM lc l
WHERE l.city NOT IN (SELECT local_city FROM matched)
