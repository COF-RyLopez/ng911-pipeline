{{ config(materialized='table') }}

-- A1-A3 (state, county, incorporated municipality) for every address point and each side of every
-- street segment. A4 (unincorporated community) and A5 (neighborhood) have no source yet.
WITH a3 AS (
    SELECT A3, GEOMETRY FROM {{ ref('mart_nena3_a3boundary') }}
),

points AS (
    SELECT 'ADPT' AS feature, county_id || ':' || agency_domain AS key, state AS A1, county AS A2, geom
    FROM {{ ref('stg_regional_addresses') }}
    UNION ALL
    -- side sample points ~5 m (0.00005 deg) left/right of each segment's midpoint, perpendicular to it
    SELECT side.feature, RCL_NGUID, 'CA', upper(County_L),
           ST_Point(ST_X(m) + side.sgn * -dy / len * 0.00005, ST_Y(m) + side.sgn * dx / len * 0.00005)
    FROM (
        SELECT RCL_NGUID, County_L, m,
               ST_X(n) - ST_X(m) AS dx, ST_Y(n) - ST_Y(m) AS dy,
               greatest(sqrt((ST_X(n) - ST_X(m)) ^ 2 + (ST_Y(n) - ST_Y(m)) ^ 2), 1e-12) AS len
        FROM (
            SELECT RCL_NGUID, County_L,
                   ST_LineInterpolatePoint(g, 0.5) AS m, ST_LineInterpolatePoint(g, 0.501) AS n
            FROM (SELECT RCL_NGUID, County_L, ST_LineMerge(ST_Geometry) AS g FROM {{ ref('mart_ng911_road_centerlines') }})
            WHERE ST_GeometryType(g) = 'LINESTRING'
        )
    ) seg
    CROSS JOIN (VALUES ('STSEG_L', 1), ('STSEG_R', -1)) side(feature, sgn)
)

SELECT p.feature, p.key, p.A1, p.A2, min(a3.A3) AS A3
FROM points p
LEFT JOIN a3 ON ST_Within(p.geom, a3.GEOMETRY)
GROUP BY p.feature, p.key, p.A1, p.A2
