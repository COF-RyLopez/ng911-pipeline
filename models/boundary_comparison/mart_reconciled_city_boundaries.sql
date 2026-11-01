{{ config(materialized='table') }}

-- Product 2: reconciled city boundaries (ADVISORY: the legal boundary is the filing with the State Board
-- of Equalization). CDTFA decides which land is in which city and keeps its statewide edges; the county's
-- line is used only where mart_boundary_discrepancies says it should be:
--   county-only SLIVER or FILED_CHANGE pieces are added (parcel-aligned linework / county ahead of CDTFA),
--   CDTFA-only SLIVER pieces are removed,
--   UNEXPLAINED and ROAD_RIGHT_OF_WAY pieces keep CDTFA's line and stay on the review list
--   (UnexplainedPiecesKept / UnexplainedKm2 count both).
-- Added pieces are clipped out of every neighbour (after the neighbour's own sliver removals), so no city
-- grows into land another city keeps. Finally the
-- boundary is snapped to parcel lines within ~4 m (vertices move onto the nearest parcel edge/vertex).
-- ponytail: 4 m snap tolerance; parcels are Fresno's, so only counties with boundary layers are snapped.
WITH st AS (
    SELECT state_city AS city, state_geom AS geom
    FROM {{ ref('int_boundary_pairs') }}
    WHERE state_geom IS NOT NULL
),
d AS (
    SELECT City AS city, Side, Cause, ST_Geometry AS geom FROM {{ ref('mart_boundary_discrepancies') }}
),
adds AS (
    SELECT city, ST_Union_Agg(geom) AS geom, count(*) AS n
    FROM d WHERE Side = 'ONLY_IN_LOCAL' AND Cause IN ('SLIVER', 'FILED_CHANGE')
    GROUP BY city
),
removes AS (
    SELECT city, ST_Union_Agg(geom) AS geom, count(*) AS n
    FROM d WHERE Side = 'ONLY_IN_STATE' AND Cause = 'SLIVER'
    GROUP BY city
),
adds_clipped AS (
    -- clip against neighbours as they stand after their own slivers are removed: a strip that moves from
    -- B to A along the county's line is taken by A, but A never takes land a neighbour keeps
    SELECT a.city, a.n,
           coalesce(ST_Difference(a.geom, (
               SELECT ST_Union_Agg(ST_Difference(o.geom, coalesce(ro.geom, ST_GeomFromText('POLYGON EMPTY'))))
               FROM st o LEFT JOIN removes ro ON ro.city = o.city
               WHERE o.city <> a.city AND ST_Intersects(o.geom, a.geom))),
                    a.geom) AS geom
    FROM adds a
),
unexplained AS (
    SELECT city, count(*) AS n, sum({{ area_km2('geom') }}) AS km2
    FROM d WHERE Cause IN ('UNEXPLAINED', 'ROAD_RIGHT_OF_WAY')
    GROUP BY city
),
merged AS (
    SELECT s.city, s.geom AS state_geom,
           ST_MakeValid(ST_Difference(
               ST_Union(s.geom, coalesce(a.geom, ST_GeomFromText('POLYGON EMPTY'))),
               coalesce(r.geom, ST_GeomFromText('POLYGON EMPTY')))) AS geom,
           coalesce(a.n, 0) AS added_pieces, coalesce(r.n, 0) AS removed_pieces,
           coalesce(u.n, 0) AS unexplained_pieces, coalesce(u.km2, 0) AS unexplained_km2
    FROM st s
    LEFT JOIN adds_clipped a USING (city)
    LEFT JOIN removes r USING (city)
    LEFT JOIN unexplained u USING (city)
),
reconciled AS (
    SELECT m.* REPLACE (
        CASE WHEN {{ 'TRUE' if county('boundary_layers') else 'FALSE' }}
             THEN coalesce(ST_MakeValid(ST_Snap(m.geom,
                      (SELECT ST_Collect(list(ST_Boundary(p.geom))) FROM {{ ref('stg_county_parcels') }} p
                       WHERE ST_DWithin(ST_Boundary(m.geom), p.geom, 0.00005)),
                      0.00004)), m.geom)
             ELSE m.geom END AS geom)
    FROM merged m
)
SELECT
    '{{ county("label") }}' AS Jurisdiction,
    city AS City,
    round({{ area_km2('geom') }}, 3) AS AreaKm2,
    round({{ area_km2('geom') }} - {{ area_km2('state_geom') }}, 3) AS ChangeFromCdtfaKm2,
    added_pieces AS PiecesTakenFromCounty,
    removed_pieces AS SliversRemoved,
    unexplained_pieces AS UnexplainedPiecesKept,
    round(unexplained_km2, 3) AS UnexplainedKm2,
    'ADVISORY: reconciled from CDTFA and county city limits; the legal boundary is the BOE filing' AS Status,
    geom AS ST_Geometry
FROM reconciled
