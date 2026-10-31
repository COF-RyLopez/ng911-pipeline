{{ config(materialized='table') }}

-- Product 1 scorecard: how far Overture data alone gets toward an NG911 dataset for the county,
-- and what it cannot supply.
WITH a AS (SELECT count(*) AS n FROM {{ ref('oo_address_points') }}),
r AS (SELECT count(*) AS n, sum(ST_Length(geom)) * 111.32 AS km FROM {{ ref('oo_road_centerlines') }}),
f AS (SELECT count(*) AS n, count(*) FILTER (WHERE NOT is_excessive_offset) AS within_50m FROM {{ ref('oo_fishbones') }}),
b AS (
    SELECT count(DISTINCT p.overture_id) AS n
    FROM {{ ref('oo_address_points') }} p
    JOIN {{ ref('stg_overture_buildings') }} bl ON ST_Within(p.geom, ST_GeomFromWKB(ST_AsWKB(bl.geom)))
),
o AS (
    SELECT sum(length_m) AS total_m,
           sum(length_m) FILTER (WHERE overture_has_road) AS covered_m,
           sum(length_m) FILTER (WHERE overture_name_agrees) AS named_m
    FROM {{ ref('oo_road_overlap') }}
)
SELECT
    '{{ county("label") }}' AS Jurisdiction,
    a.n AS Address_Points,
    round(b.n * 100.0 / nullif(a.n, 0), 2) AS Pct_Addresses_In_Building,
    r.n AS Road_Segments,
    round(r.km, 1) AS Road_Km,
    (SELECT count(*) FROM {{ ref('oo_localities') }}) AS Localities,
    f.n AS Addresses_Matched_To_Road,
    round(f.n * 100.0 / nullif(a.n, 0), 2) AS Pct_Addresses_Matched_To_Road,
    round(f.within_50m * 100.0 / nullif(f.n, 0), 2) AS Pct_Matched_Within_50m,
    round(o.covered_m * 100.0 / nullif(o.total_m, 0), 2) AS Pct_County_Centerline_Length_In_Overture,
    round(o.named_m * 100.0 / nullif(o.total_m, 0), 2) AS Pct_County_Centerline_Length_Same_Name,
    -- What Overture does not carry (the gap Product 2 fills from county sources)
    FALSE AS Has_PSAP_Or_ESB_Boundaries,
    FALSE AS Has_Published_Address_Ranges,
    FALSE AS Has_MSAG_Or_ESN
FROM a, r, f, b, o
