{{ config(
    materialized='table'
) }}

-- NENA v3.0 Relational Data Model: ng911.DiscrpAg (Discrepancy Agency)
WITH agencies AS (
    SELECT DISTINCT
        agency_domain AS DiscrpAgID,
        source_agency AS Agency_Name
    FROM {{ ref('stg_regional_addresses') }}
)

SELECT
    row_number() OVER (ORDER BY DiscrpAgID) AS ID,
    DiscrpAgID,
    Agency_Name,
    'contact@' || DiscrpAgID AS Contact,
    current_timestamp AS DateUpdate
FROM agencies
