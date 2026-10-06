{{ config(materialized='view') }}

WITH cad_psap AS (
    SELECT 
        'PSAP' AS agency_type,
        coalesce(LE_NGUID, 'urn:emergency:uid:gis:PSAP:' || OBJECTID || ':{{ var("agency_domain", "fresnocountyca.gov") }}') AS esb_nguid,
        upper(trim(NAME)) AS agency_name,
        coalesce(trim(AGENCY), 'SO') AS agency_code,
        trim(ServiceNum) AS service_number,
        trim(NO_AREA) AS area_code,
        geom
    FROM read_parquet('data/cache/county_cad_psap.parquet')
    WHERE geom IS NOT NULL
),

fire_districts AS (
    SELECT
        'FIRE' AS agency_type,
        'urn:emergency:uid:gis:ESB:FIRE:' || CD_FIREDIST || ':' || OBJECTID || ':{{ var("agency_domain", "fresnocountyca.gov") }}' AS esb_nguid,
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
        'urn:emergency:uid:gis:BOUNDARY:MUNI:' || AGENCY_CODE || ':' || OBJECTID || ':{{ var("agency_domain", "fresnocountyca.gov") }}' AS esb_nguid,
        upper(trim(AGENCY_NAME)) AS agency_name,
        trim(AGENCY_CODE) AS agency_code,
        NULL::VARCHAR AS service_number,
        NULL::VARCHAR AS area_code,
        geom
    FROM read_parquet('data/cache/county_city_limits.parquet')
    WHERE geom IS NOT NULL
)

SELECT * FROM cad_psap
UNION ALL
SELECT * FROM fire_districts
UNION ALL
SELECT * FROM city_limits
