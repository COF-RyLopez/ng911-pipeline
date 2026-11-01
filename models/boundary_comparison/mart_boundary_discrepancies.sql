{{ config(materialized='table') }}

-- Product 2: the areas where county city limits and CDTFA disagree, one polygon per piece, for the map
-- and for handing back to the county / LAFCo, each with a likely cause:
--   FILED_CHANGE  half or more of the piece lies in a boundary change filed with the state (Gov. Code 54900):
--                 a timing difference between the two sources, not an error in either
--   ROAD_RIGHT_OF_WAY  10-100 m wide with a county road centerline along half its length or more: the
--                 sources disagree on whether the city includes the road (e.g. SR-99 at Kingsburg). That is
--                 a jurisdiction question, not a drawing error, so the reconciled boundary keeps CDTFA's line
--   SLIVER        under 50 m wide on average: the same line drawn twice, fixable by snapping to parcels
--   UNEXPLAINED   neither: a real disagreement for the county or LAFCo to resolve
-- Pieces under 1 ha are digitizing noise and are dropped.
-- ponytail: 1 ha / 50 m / 50% cutoffs. 50 m (was 25) because the county layer is better parcel-aligned than
-- CDTFA in all 15 Fresno cities; the next unexplained piece up is 57 m wide.
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
pieces AS MATERIALIZED (  -- computed once: row_number() OVER () must give each piece one id across every join
    SELECT row_number() OVER () AS piece_id, city, side, geom
    FROM (SELECT city, side, unnest(ST_Dump(geom), recursive := true) FROM diffs)  -- -> geom, path
    WHERE ST_Dimension(geom) = 2
      AND {{ area_km2('geom') }} >= 0.01
      AND {{ 'TRUE' if county('boundary_layers') else 'FALSE' }}  -- no local layer: nothing to disagree with
),
filed AS (
    SELECT p.piece_id, c.layer_name, c.props_json,
           ST_Area(ST_Intersection(p.geom, c.geom)) / nullif(ST_Area(p.geom), 0) AS share
    FROM pieces p
    JOIN {{ ref('stg_cdtfa_boundary_changes') }} c ON ST_Intersects(p.geom, c.geom)
    QUALIFY row_number() OVER (PARTITION BY p.piece_id ORDER BY share DESC) = 1
),
-- county road centerline length inside each piece, against the piece's length (~ half its perimeter)
roads AS (
    SELECT p.piece_id,
           sum(ST_Length(ST_Intersection(r.ST_Geometry, p.geom))) / nullif(ST_Perimeter(any_value(p.geom)) / 2, 0) AS road_share
    FROM pieces p
    JOIN {{ ref('mart_ng911_road_centerlines') }} r ON ST_Intersects(r.ST_Geometry, p.geom)
    GROUP BY p.piece_id
)
SELECT
    '{{ county("label") }}' AS Jurisdiction,
    p.city AS City,
    p.side AS Side,
    round({{ area_km2('p.geom') }}, 4) AS AreaKm2,
    -- mean width ~ 2 x area / perimeter; perimeter scaled by sqrt(cos lat) (a mid-orientation estimate)
    round(2 * {{ area_km2('p.geom') }} * 1e6
          / nullif(ST_Perimeter(p.geom) * 111320 * sqrt(cos(radians(ST_Y(ST_Centroid(p.geom))))), 0), 1) AS MeanWidthM,
    CASE
        WHEN f.share >= 0.5 THEN 'FILED_CHANGE'
        -- a right-of-way is a strip: under 100 m (wide freeways like SR-99 fit); without the cap, a large area
        -- full of streets (Fresno's ~26 km2 county-only area) passed as one
        WHEN MeanWidthM >= 10 AND MeanWidthM < 100 AND rd.road_share >= 0.5 THEN 'ROAD_RIGHT_OF_WAY'
        WHEN MeanWidthM < 50 THEN 'SLIVER'
        ELSE 'UNEXPLAINED'
    END AS Cause,
    round(100 * f.share, 1) AS PctInFiledChange,
    round(100 * least(coalesce(rd.road_share, 0), 1), 1) AS PctLengthAlongRoad,  -- least() skips NULLs, so coalesce first
    f.layer_name AS FiledChangeLayer,
    f.props_json AS FiledChangeRecord,
    p.geom AS ST_Geometry
FROM pieces p
LEFT JOIN filed f USING (piece_id)
LEFT JOIN roads rd USING (piece_id)
