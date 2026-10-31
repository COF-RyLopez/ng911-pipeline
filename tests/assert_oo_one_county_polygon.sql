-- Product 1 is clipped to this polygon; a county-name mismatch with Overture divisions would
-- silently empty every oo_ model, so fail unless exactly one polygon was found.
SELECT count(*) AS polygons
FROM {{ ref('oo_county_boundary') }}
HAVING count(*) != 1
