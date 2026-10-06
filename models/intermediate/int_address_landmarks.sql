{{ config(materialized='view') }}

WITH addr AS (
    SELECT 
        coalesce(county_id, gers_id) AS addr_uid,
        longitude,
        latitude,
        floor(longitude * 50)::INTEGER AS gx,
        floor(latitude * 50)::INTEGER AS gy,
        geom
    FROM {{ ref('int_address_conflation') }}
    WHERE geom IS NOT NULL
),

places AS (
    SELECT 
        place_id,
        place_name,
        taxonomy_category,
        floor(longitude * 50)::INTEGER AS gx,
        floor(latitude * 50)::INTEGER AS gy,
        geom
    FROM {{ ref('stg_overture_places') }}
    WHERE geom IS NOT NULL
),

ranked_matches AS (
    SELECT 
        a.addr_uid,
        p.place_name,
        p.taxonomy_category,
        ST_Distance_Sphere(a.geom, p.geom) AS landmark_distance_meters,
        ROW_NUMBER() OVER (
            PARTITION BY a.addr_uid 
            ORDER BY ST_Distance(a.geom, p.geom) ASC
        ) as rn
    FROM addr a
    JOIN places p
      ON a.gx = p.gx AND a.gy = p.gy
     AND ST_DWithin(a.geom, p.geom, 0.0006)
)

SELECT
    addr_uid,
    place_name AS landmark_name,
    taxonomy_category AS landmark_category,
    round(landmark_distance_meters, 1) AS landmark_distance_meters
FROM ranked_matches
WHERE rn = 1 
  AND landmark_distance_meters <= 60.0
