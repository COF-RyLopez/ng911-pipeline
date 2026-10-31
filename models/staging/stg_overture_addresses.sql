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
    {%- set b = county('bbox') %}
    WHERE bbox.xmin >= {{ b[0] }} AND bbox.xmax <= {{ b[2] }}
      AND bbox.ymin >= {{ b[1] }} AND bbox.ymax <= {{ b[3] }}
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
        coalesce(upper(trim(overture_city)), '{{ county("name") }}') AS community_name,
        nullif(trim(overture_postcode), '') AS postcode,
        '{{ county("name") }}' AS county,
        'CA' AS state,
        'US' AS country,
        ST_X(overture_geom) AS longitude,
        ST_Y(overture_geom) AS latitude,
        overture_geom AS geom,
        'OVERTURE' AS source_agency
    FROM raw_overture
    -- an address with no street cannot be an SSAP (NENA STN is mandatory)
    WHERE overture_number IS NOT NULL
      AND nullif(trim(overture_street), '') IS NOT NULL
)

SELECT * FROM parsed_overture
