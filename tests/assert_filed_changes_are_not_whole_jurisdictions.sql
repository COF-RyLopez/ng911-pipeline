-- A filed change is an annexation / detachment / correction, far smaller than a whole city or county.
-- Anything over 100 km2 means a base jurisdiction layer slipped into stg_cdtfa_boundary_changes again.
SELECT layer_name, round({{ area_km2('geom') }}, 1) AS km2
FROM {{ ref('stg_cdtfa_boundary_changes') }}
WHERE {{ area_km2('geom') }} > 100
