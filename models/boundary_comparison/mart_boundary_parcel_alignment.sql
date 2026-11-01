{{ config(materialized='table') }}

-- Product 2: how much of each city's boundary runs along a parcel line (within ~3 m), for CDTFA, the
-- county layer and the reconciled boundary, sampled every ~10 m along the boundary. Evidence for the
-- reconciliation rules: the reconciled boundary should be at least as well aligned as either source.
-- ponytail: city limits along roads often follow the centreline, not a parcel edge, so no source reaches
-- 100%; compare sources against each other. Parcels are Fresno's: runs only for counties with boundary layers.
WITH lines AS (
    SELECT p.state_city AS city, s.source, s.geom
    FROM {{ ref('int_boundary_pairs') }} p,
         LATERAL (VALUES ('CDTFA', p.state_geom), ('COUNTY', p.local_geom)) s(source, geom)
    WHERE p.state_geom IS NOT NULL AND p.local_geom IS NOT NULL
    UNION ALL
    SELECT r.City, 'RECONCILED', r.ST_Geometry
    FROM {{ ref('mart_reconciled_city_boundaries') }} r
    JOIN {{ ref('int_boundary_pairs') }} p ON p.state_city = r.City AND p.local_geom IS NOT NULL
),
rings AS (
    SELECT city, source, geom AS ring
    FROM (SELECT city, source, unnest(ST_Dump(ST_Boundary(geom)), recursive := true) FROM lines)
    WHERE {{ 'TRUE' if county('boundary_layers') else 'FALSE' }}
),
samples AS (
    SELECT city, source, unnest(ST_Dump(ST_LineInterpolatePoints(ring,
               least(1.0, 0.0001 / nullif(ST_Length(ring), 0)), true)), recursive := true)  -- ~every 10 m
    FROM rings
)
SELECT
    '{{ county("label") }}' AS Jurisdiction,
    s.city AS City,
    s.source AS Source,
    count(*) AS SamplePoints,
    round(100.0 * count(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM {{ ref('stg_county_parcels') }} p
        WHERE ST_DWithin(s.geom, p.geom, 0.00003)
          AND ST_Distance(s.geom, ST_Boundary(p.geom)) <= 0.00003)) / count(*), 1) AS PctOnParcelLines
FROM samples s
GROUP BY 1, 2, 3
