{{ config(
    materialized='table'
) }}

-- NENA v3.0 Relational Data Model: ng911.DiscrpAg (Discrepancy Agency)
WITH agencies AS (
    SELECT 
        agency_domain AS DiscrpAgID,
        max(source_agency) AS Agency_Name
    FROM {{ ref('stg_regional_addresses') }}
    GROUP BY agency_domain
)

SELECT
    row_number() OVER (ORDER BY DiscrpAgID) AS ID,
    DiscrpAgID,
    Agency_Name,
    'contact@' || DiscrpAgID AS Contact,
    current_timestamp AS DateUpdate
FROM agencies
