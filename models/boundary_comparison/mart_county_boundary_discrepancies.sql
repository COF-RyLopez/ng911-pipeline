{{ config(materialized='table') }}

-- Product 2: where Overture's or TIGER's county polygon disagrees with CDTFA's, one polygon per piece
-- (1 ha and up), with how many of the county's own address points sit in it. Points in an ONLY_IN_STATE
-- piece are inside the state's county line but outside the other source's; points in ONLY_IN_OTHER are the
-- reverse. Cause: SLIVER (under 25 m mean width: the same line drawn twice) or UNEXPLAINED.
-- ponytail: 1 ha / 25 m cutoffs match the city comparison; county lines generalized at TIGER scale may
-- need a wider sliver cutoff.
WITH frame AS (SELECT geom FROM {{ ref('int_county_boundary_sources') }} WHERE source = 'CDTFA' AND geom IS NOT NULL),
others AS (SELECT source, geom FROM {{ ref('int_county_boundary_sources') }} WHERE source <> 'CDTFA' AND geom IS NOT NULL),
diffs AS (
    SELECT o.source, 'ONLY_IN_STATE' AS side, ST_Difference(f.geom, o.geom) AS geom FROM frame f, others o
    UNION ALL
    SELECT o.source, 'ONLY_IN_OTHER', ST_Difference(o.geom, f.geom) FROM frame f, others o
),
pieces AS MATERIALIZED (  -- computed once: row_number() OVER () must give each piece one id across every join
    SELECT row_number() OVER () AS piece_id, source, side, geom
    FROM (SELECT source, side, unnest(ST_Dump(geom), recursive := true) FROM diffs)  -- -> geom, path
    WHERE ST_Dimension(geom) = 2 AND {{ area_km2('geom') }} >= 0.01
),
pts AS (
    SELECT p.piece_id, count(*) AS n
    FROM pieces p
    JOIN {{ ref('stg_county_addresses') }} a ON ST_Within(a.geom, p.geom)
    GROUP BY 1
)
SELECT
    '{{ county("label") }}' AS Jurisdiction,
    p.source AS ComparedTo,
    p.side AS Side,
    round({{ area_km2('p.geom') }}, 4) AS AreaKm2,
    round(2 * {{ area_km2('p.geom') }} * 1e6
          / nullif(ST_Perimeter(p.geom) * 111320 * sqrt(cos(radians(ST_Y(ST_Centroid(p.geom))))), 0), 1) AS MeanWidthM,
    CASE WHEN MeanWidthM < 25 THEN 'SLIVER' ELSE 'UNEXPLAINED' END AS Cause,
    coalesce(t.n, 0) AS CountyAddressPoints,
    p.geom AS ST_Geometry
FROM pieces p
LEFT JOIN pts t USING (piece_id)
