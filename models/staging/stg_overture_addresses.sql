{{ config(materialized='view') }}

WITH raw_overture AS (
    {% if var('use_cached_data', true) %}
    SELECT *
    FROM read_parquet('data/cache/overture_addresses.parquet')
    {% else %}
    SELECT
        id AS overture_id,
        geometry AS overture_geom,
        number AS overture_number,
        street AS overture_street,
        postcode AS overture_postcode,
        postal_city AS overture_city,
        bbox.xmin AS minx,
        bbox.xmax AS maxx,
        bbox.ymin AS miny,
        bbox.ymax AS maxy
    FROM read_parquet('s3://overturemaps-us-west-2/release/2026-09-23.1/theme=addresses/type=address/*.parquet')
    WHERE bbox.xmin >= {{ var('bbox_minx', -119.95) }} AND bbox.xmax <= {{ var('bbox_maxx', -119.65) }}
      AND bbox.ymin >= {{ var('bbox_miny', 36.65) }}   AND bbox.ymax <= {{ var('bbox_maxy', 36.90) }}
    {% endif %}
),

parsed_overture AS (
    SELECT
        overture_id,
        upper(trim(overture_number)) AS house_number,
        {{ normalize_direction("nullif(regexp_extract(upper(trim(overture_street)), '^(N|S|E|W|NE|NW|SE|SW|NORTH|SOUTH|EAST|WEST)\\\\s+', 1), '')") }} AS pre_directional,
        trim(regexp_replace(
            regexp_replace(
                upper(trim(overture_street)),
                '^(N|S|E|W|NE|NW|SE|SW|NORTH|SOUTH|EAST|WEST)\\\\s+', ''
            ),
            '\\\\s+(ST|AVE|BLVD|RD|DR|LN|WAY|CT|PL|CIR|HWY|PKWY|TRL|LOOP)$', ''
        )) AS street_name,
        {{ normalize_street_type("nullif(regexp_extract(upper(trim(overture_street)), '\\\\s+(ST|AVE|BLVD|RD|DR|LN|WAY|CT|PL|CIR|HWY|PKWY|TRL|LOOP)$', 1), '')") }} AS street_type,
        coalesce(upper(trim(overture_city)), 'FRESNO') AS community_name,
        nullif(trim(overture_postcode), '') AS postcode,
        'FRESNO' AS county,
        'CA' AS state,
        'US' AS country,
        ST_X(overture_geom) AS longitude,
        ST_Y(overture_geom) AS latitude,
        overture_geom AS geom,
        'OVERTURE' AS source_agency
    FROM raw_overture
    WHERE overture_number IS NOT NULL
)

SELECT * FROM parsed_overture
