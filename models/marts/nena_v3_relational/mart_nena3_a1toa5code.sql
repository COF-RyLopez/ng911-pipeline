{{ config(materialized='table') }}

-- NENA v3.0 Relational Data Model: ng911.A1toA5Code
SELECT row_number() OVER (ORDER BY A1, A2, A3) AS ID, A1, A2, A3, NULL::VARCHAR AS A4, NULL::VARCHAR AS A5
FROM (SELECT DISTINCT A1, A2, A3 FROM {{ ref('int_nena3_admin_areas') }})
