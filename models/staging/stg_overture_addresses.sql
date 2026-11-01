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
        sources[1].dataset AS source_dataset,
        sources[1].record_id AS source_record_id,
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

-- street is read with trailing periods dropped: some sources write types as "ST." (Glenn: 'SHASTA ST.'),
-- which the type-suffix regex below would otherwise miss, leaving the type in the street name
parsed_overture AS (
    SELECT
        overture_id,
        upper(trim(overture_number)) AS house_number,
        -- type suffix comes off first, so "E ST" (E Street) keeps "E" as its name rather than "ST"
        {{ normalize_direction("nullif(regexp_extract(regexp_replace(regexp_replace(upper(trim(overture_street)), '[.]+$', ''), ' +(ST|AVE|BLVD|RD|DR|LN|WAY|CT|PL|CIR|HWY|PKWY|TRL|LOOP)$', ''), '^(N|S|E|W|NE|NW|SE|SW|NORTH|SOUTH|EAST|WEST) +', 1), '')") }} AS pre_directional,
        nullif(trim(regexp_replace(
            regexp_replace(regexp_replace(upper(trim(overture_street)), '[.]+$', ''), ' +(ST|AVE|BLVD|RD|DR|LN|WAY|CT|PL|CIR|HWY|PKWY|TRL|LOOP)$', ''),
            '^(N|S|E|W|NE|NW|SE|SW|NORTH|SOUTH|EAST|WEST) +', ''
        )), '') AS street_name,
        {{ normalize_street_type("nullif(regexp_extract(regexp_replace(upper(trim(overture_street)), '[.]+$', ''), ' +(ST|AVE|BLVD|RD|DR|LN|WAY|CT|PL|CIR|HWY|PKWY|TRL|LOOP)$', 1), '')") }} AS street_type,
        coalesce(upper(trim(overture_city)), '{{ county("name") }}') AS community_name,
        nullif(trim(overture_postcode), '') AS postcode,
        '{{ county("name") }}' AS county,
        'CA' AS state,
        'US' AS country,
        ST_X(overture_geom) AS longitude,
        ST_Y(overture_geom) AS latitude,
        overture_geom AS geom,
        'OVERTURE' AS source_agency,
        source_dataset,     -- lineage: the dataset Overture republished (an OpenAddresses source path)
        source_record_id
    FROM raw_overture
    WHERE overture_number IS NOT NULL
)

SELECT * FROM parsed_overture
