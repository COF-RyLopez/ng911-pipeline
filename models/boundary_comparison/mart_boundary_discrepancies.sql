{{ config(materialized='table') }}

-- Product 2: the areas where county city limits and CDTFA disagree, one polygon per piece, for the map
-- and for handing back to the county / LAFCo. Pieces under 1 ha are digitizing slivers and are dropped.
-- ponytail: 1 ha cutoff; lower it if annexation-sized parcels go missing from the review list.
WITH diffs AS (
    SELECT coalesce(state_city, local_city) AS city, 'ONLY_IN_STATE' AS side,
           ST_Difference(state_geom, coalesce(local_geom, ST_GeomFromText('POLYGON EMPTY'))) AS geom
    FROM {{ ref('int_boundary_pairs') }}
    WHERE state_geom IS NOT NULL
    UNION ALL
    SELECT coalesce(state_city, local_city), 'ONLY_IN_LOCAL',
           ST_Difference(local_geom, coalesce(state_geom, ST_GeomFromText('POLYGON EMPTY')))
    FROM {{ ref('int_boundary_pairs') }}
    WHERE local_geom IS NOT NULL
),
pieces AS (
    SELECT city, side, unnest(ST_Dump(geom), recursive := true)  -- -> geom, path
    FROM diffs
)
SELECT
    '{{ county("label") }}' AS Jurisdiction,
    city AS City,
    side AS Side,
    round({{ area_km2('geom') }}, 4) AS AreaKm2,
    geom AS ST_Geometry
FROM pieces
WHERE ST_Dimension(geom) = 2
  AND {{ area_km2('geom') }} >= 0.01
  AND {{ 'TRUE' if county('boundary_layers') else 'FALSE' }}  -- no local layer: nothing to disagree with
