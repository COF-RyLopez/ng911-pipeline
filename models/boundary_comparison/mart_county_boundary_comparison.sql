{{ config(materialized='table') }}

-- Product 2: the county's polygon from Overture and TIGER, each compared with CDTFA's, plus how many of
-- the county's own address points fall outside CDTFA's county line (points another county should own,
-- or points placed outside the county by mistake).
WITH frame AS (SELECT geom FROM {{ ref('int_county_boundary_sources') }} WHERE source = 'CDTFA'),
others AS (SELECT source, geom FROM {{ ref('int_county_boundary_sources') }} WHERE source <> 'CDTFA'),
outside AS (
    SELECT count(*) FILTER (WHERE NOT ST_Within(a.geom, f.geom)) AS n, count(*) AS total
    FROM {{ ref('stg_county_addresses') }} a, frame f
),
d AS (
    SELECT ComparedTo, sum(AreaKm2) FILTER (WHERE Cause = 'UNEXPLAINED') AS unexplained_km2,
           sum(CountyAddressPoints) AS pts
    FROM {{ ref('mart_county_boundary_discrepancies') }}
    GROUP BY 1
)
SELECT
    '{{ county("label") }}' AS Jurisdiction,
    o.source AS ComparedTo,
    round({{ area_km2('f.geom') }}, 2) AS CdtfaAreaKm2,
    round({{ area_km2('o.geom') }}, 2) AS OtherAreaKm2,
    round(100.0 * ST_Area(ST_Intersection(f.geom, o.geom))
          / nullif(ST_Area(ST_Union(f.geom, o.geom)), 0), 3) AS PctAgreement,
    round(coalesce(d.unexplained_km2, 0), 3) AS UnexplainedKm2,
    coalesce(d.pts, 0) AS AddressPointsInDisagreement,
    x.n AS CountyAddressPointsOutsideCdtfa,
    x.total AS CountyAddressPoints
FROM frame f
CROSS JOIN others o
CROSS JOIN outside x
LEFT JOIN d ON d.ComparedTo = o.source
WHERE f.geom IS NOT NULL AND o.geom IS NOT NULL
