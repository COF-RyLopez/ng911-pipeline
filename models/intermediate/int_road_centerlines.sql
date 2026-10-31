{{ config(materialized='table') }}

-- One row per road geometry with its primary (addressing-authority) street name.
-- County sources repeat some geometries: exact duplicates (37 in Fresno) and alias names
-- (e.g. HIGHWAY 43 / 8TH AVE in Kings, AVENUE 200 / EAST RANKIN AVENUE in Tulare).
-- NENA-STA-006: the RCL carries the locally assigned name; other names are aliases.
-- Primary = the name the nearby address points use; tie -> the copy with published ranges;
-- still tied -> alphabetical, flagged UNRESOLVED for county review.

WITH s AS (
    SELECT * FROM {{ ref('stg_county_streets') }}
),

shared AS (
    SELECT street_segment_id
    FROM s
    GROUP BY 1
    HAVING count(DISTINCT full_street_name) > 1
),

candidates AS (
    SELECT DISTINCT s.street_segment_id, s.full_street_name, s.street_name, s.geom
    FROM s JOIN shared USING (street_segment_id)
),

votes AS (
    SELECT c.street_segment_id, c.full_street_name, count(a.street_name) AS addr_votes
    FROM candidates c
    LEFT JOIN {{ ref('stg_regional_addresses') }} a
      ON ST_Intersects(a.geom, ST_Buffer(c.geom, 0.0009))           -- ~100 m: rural address points sit well back from the road
     AND (a.street_name = c.street_name
          OR c.street_name LIKE '% ' || a.street_name)               -- Tulare points store 'AVENUE 28' as '28'
    GROUP BY 1, 2
),

ranked AS (
    SELECT
        s.*,
        coalesce(v.addr_votes, 0) AS addr_votes,
        row_number() OVER w AS rn,
        count(DISTINCT s.full_street_name) OVER (PARTITION BY s.street_segment_id) AS name_count
    FROM s
    LEFT JOIN votes v USING (street_segment_id, full_street_name)
    WINDOW w AS (PARTITION BY s.street_segment_id
                 ORDER BY coalesce(v.addr_votes, 0) DESC, s.has_published_ranges DESC, s.full_street_name, s.oa_source)
),

decided AS (
    SELECT
        street_segment_id,
        CASE
            WHEN max(name_count) = 1 THEN NULL
            WHEN max(addr_votes) > 0
                 AND max(addr_votes) FILTER (WHERE rn = 1) > coalesce(max(addr_votes) FILTER (WHERE rn > 1), 0) THEN 'ADDRESS_POINTS'
            WHEN count(*) FILTER (WHERE has_published_ranges) = 1 THEN 'PUBLISHED_RANGES'
            ELSE 'UNRESOLVED'
        END AS primary_name_method,
        string_agg(DISTINCT full_street_name, '; ' ORDER BY full_street_name)
            FILTER (WHERE rn > 1 AND full_street_name <> primary_name) AS alias_names
    FROM (SELECT *, first_value(full_street_name) OVER (PARTITION BY street_segment_id ORDER BY rn) AS primary_name FROM ranked)
    GROUP BY 1
)

SELECT r.* EXCLUDE (rn, name_count, addr_votes), d.primary_name_method, d.alias_names
FROM ranked r
JOIN decided d USING (street_segment_id)
WHERE r.rn = 1
