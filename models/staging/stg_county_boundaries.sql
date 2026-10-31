{{ config(materialized='view') }}

-- City_County_CAD ("Dispatch Areas: City vs County") holds law enforcement dispatch areas
-- (Sheriff, city PDs, SCCCD, CSUF, Coalinga State Hospital), not PSAP boundaries: NENA's ESB Law layer.
WITH cad_law AS (
    SELECT 
        'LAW' AS agency_type,
        coalesce(LE_NGUID, 'urn:emergency:uid:gis:LAW:' || OBJECTID || ':{{ county("agency_domain") }}') AS esb_nguid,
        upper(trim(NAME)) AS agency_name,
        coalesce(trim(AGENCY), 'SO') AS agency_code,
        trim(ServiceNum) AS service_number,
        trim(NO_AREA) AS area_code,
        ST_MakeValid(geom) AS geom  -- 6 source polygons are invalid; see mart_ng911_esb_qa
    FROM read_parquet('data/cache/county_cad_psap.parquet')
    WHERE geom IS NOT NULL
),

fire_districts AS (
    SELECT
        'FIRE' AS agency_type,
        'urn:emergency:uid:gis:ESB:FIRE:' || CD_FIREDIST || ':' || OBJECTID || ':{{ county("agency_domain") }}' AS esb_nguid,
        upper(trim(NM_FIREDIST)) AS agency_name,
        trim(CD_FIREDIST) AS agency_code,
        NULL::VARCHAR AS service_number,
        NULL::VARCHAR AS area_code,
        geom
    FROM read_parquet('data/cache/county_fire_districts.parquet')
    WHERE geom IS NOT NULL
),

city_limits AS (
    SELECT
        'MUNICIPAL' AS agency_type,
        'urn:emergency:uid:gis:BOUNDARY:MUNI:' || AGENCY_CODE || ':' || OBJECTID || ':{{ county("agency_domain") }}' AS esb_nguid,
        upper(trim(AGENCY_NAME)) AS agency_name,
        trim(AGENCY_CODE) AS agency_code,
        NULL::VARCHAR AS service_number,
        NULL::VARCHAR AS area_code,
        geom
    FROM read_parquet('data/cache/county_city_limits.parquet')
    WHERE geom IS NOT NULL
)

-- These are Fresno's layers; a county without boundary_layers gets no rows rather than Fresno's polygons.
SELECT * FROM (
    SELECT * FROM cad_law
    UNION ALL
    SELECT * FROM fire_districts
    UNION ALL
    SELECT * FROM city_limits
)
WHERE {{ 'TRUE' if county('boundary_layers') else 'FALSE' }}
