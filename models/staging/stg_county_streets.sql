{{ config(materialized='view') }}

-- Road centerlines from OpenAddresses' processed county sources
-- (scripts/fetch_pilot_data.py -> fetch_oa_centerlines). OA delivers one joined
-- street name, so it is split back into NENA components here.
-- One row per source record: shared geometries (duplicates and alias names) are resolved in
-- int_road_centerlines.
-- ponytail: suffix-type list is a common-USPS subset; extend it if parsed types look wrong.

WITH raw AS (
    SELECT *
    FROM read_parquet('data/cache/oa_centerlines.parquet')
    WHERE name IS NOT NULL
    {% if not var('include_surrounding_counties', false) %}
      AND county_name = '{{ county("name") }}'
    {% endif %}
),

tok AS (
    SELECT *, string_split(regexp_replace(upper(trim(name)), '\s+', ' ', 'g'), ' ') AS t0
    FROM raw
),

-- Peel components off the ends: post-direction, then street type, then pre-direction.
-- Each step needs a token left over, so "NORTH AVE" stays name=NORTH, type=AVE.
post AS (
    SELECT *,
        CASE WHEN len(t0) >= 3 AND t0[-1] IN {{ dirs() }} THEN t0[-1] END AS post_dir_raw,
        CASE WHEN len(t0) >= 3 AND t0[-1] IN {{ dirs() }} THEN t0[1:-2] ELSE t0 END AS t1
    FROM tok
),
typ AS (
    SELECT *,
        CASE WHEN len(t1) >= 2 AND t1[-1] IN {{ street_types() }} THEN t1[-1] END AS type_raw,
        CASE WHEN len(t1) >= 2 AND t1[-1] IN {{ street_types() }} THEN t1[1:-2] ELSE t1 END AS t2
    FROM post
),
pre AS (
    SELECT *,
        CASE WHEN len(t2) >= 2 AND t2[1] IN {{ dirs() }} THEN t2[1] END AS pre_dir_raw,
        CASE WHEN len(t2) >= 2 AND t2[1] IN {{ dirs() }} THEN t2[2:] ELSE t2 END AS t3
    FROM typ
)

SELECT
    lower(county_name) || '-' || substr(md5(ST_AsHEXWKB(geom)), 1, 12) AS street_segment_id,
    id AS str_id,                       -- source segment id where the county publishes one (e.g. Tulare NGUID)
    county_name AS agency_code,
    county_name,
    oa_source,
    {{ normalize_direction('pre_dir_raw') }} AS pre_directional,
    array_to_string(t3, ' ') AS street_name,
    {{ normalize_street_type('type_raw') }} AS street_type,
    {{ normalize_direction('post_dir_raw') }} AS post_directional,
    CASE classification
        WHEN 'motorway' THEN 'Freeway'
        WHEN 'trunk' THEN 'Expressway'
        WHEN 'primary' THEN 'Super Arterial'
        WHEN 'secondary' THEN 'Arterial'
        WHEN 'tertiary' THEN 'Collector'
        WHEN 'service' THEN 'Private'
        ELSE 'Local'
    END AS road_class,
    lower(classification) AS source_classification,
    trim(concat_ws(' ',
        {{ normalize_direction('pre_dir_raw') }},
        array_to_string(t3, ' '),
        {{ normalize_street_type('type_raw') }},
        {{ normalize_direction('post_dir_raw') }}
    )) AS full_street_name,
    -- Published attributes (NULL where the county doesn't publish them)
    nullif(TRY_CAST(addr_from_left AS INTEGER), 0) AS pub_from_addr_l,
    nullif(TRY_CAST(addr_to_left AS INTEGER), 0) AS pub_to_addr_l,
    nullif(TRY_CAST(addr_from_right AS INTEGER), 0) AS pub_from_addr_r,
    nullif(TRY_CAST(addr_to_right AS INTEGER), 0) AS pub_to_addr_r,
    coalesce(nullif(TRY_CAST(addr_from_left AS INTEGER), 0), nullif(TRY_CAST(addr_from_right AS INTEGER), 0)) IS NOT NULL AS has_published_ranges,
    zip_left,
    zip_right,
    round(TRY_CAST(speed AS DOUBLE) / 1.609344)::INTEGER AS speed_mph,   -- OA speed is km/h
    CASE oneway WHEN 'yes' THEN 'FT' WHEN 'reverse' THEN 'TF' WHEN 'no' THEN 'B' END AS one_way,
    geom
FROM pre
WHERE len(t3) > 0
  -- unnamed segments arrive named by their type alone (e.g. Fresno's 1,408 'Aly'); the county leaves STR_NAME empty
  AND NOT (len(t0) = 1 AND t0[1] IN {{ street_types() }})
