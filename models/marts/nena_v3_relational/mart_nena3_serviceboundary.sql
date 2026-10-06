{{ config(
    materialized='table'
) }}

-- NENA v3.0 Relational Data Model: ng911.ServiceBoundary
WITH boundaries AS (
    SELECT *
    FROM {{ ref('mart_ng911_emergency_boundaries') }}
),

agencies AS (
    SELECT ID AS DiscrpAg_ID, DiscrpAgID
    FROM {{ ref('mart_nena3_discrpag') }}
),

urns AS (
    SELECT ID AS ServiceURN_ID, ServiceURN
    FROM {{ ref('mart_nena3_serviceurn') }}
)

SELECT
    row_number() OVER () AS ID,
    b.ST_Geometry AS GEOMETRY,
    coalesce(ag.DiscrpAg_ID, 1) AS DiscrpAg_ID,
    current_timestamp AS DateUpdate,
    b.ESB_NGUID AS NGUID,
    b.Agency_Code AS Agency_ID,
    'sip:' || lower(coalesce(b.Agency_Code, 'dispatch')) || '@' || b.DisclID AS ServiceURI,
    CASE b.Agency_Type
        WHEN 'FIRE' THEN 2
        WHEN 'PSAP' THEN 3
        ELSE 1
    END AS ServiceURN_ID,
    b.ServiceNum,
    'https://' || b.DisclID || '/vcard' AS AVcard_URI,
    b.Agency_Name AS DsplayNam
FROM boundaries b
LEFT JOIN agencies ag
  ON b.DisclID = ag.DiscrpAgID
