-- CDTFA must return the county's own polygon; none means the fetch or the name filter broke.
SELECT 1
FROM (SELECT count(*) AS n FROM {{ ref('int_county_boundary_sources') }} WHERE source = 'CDTFA' AND geom IS NOT NULL)
WHERE n = 0
