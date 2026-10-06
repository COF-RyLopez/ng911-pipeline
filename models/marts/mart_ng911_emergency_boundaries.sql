{{ config(
    materialized='table'
) }}

WITH staged_boundaries AS (
    SELECT * FROM {{ ref('stg_county_boundaries') }}
)

SELECT
    '{{ var("agency_domain", "fresnocountyca.gov") }}' AS DisclID,
    esb_nguid AS ESB_NGUID,
    agency_type AS Agency_Type,
    agency_name AS Agency_Name,
    agency_code AS Agency_Code,
    service_number AS ServiceNum,
    area_code AS Area_Code,
    current_timestamp AS DateUpdate,
    geom AS ST_Geometry
FROM staged_boundaries
