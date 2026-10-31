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
    coalesce(d.last_published, current_date) AS DateUpdate,
    b.ESB_NGUID AS NGUID,
    b.Agency_Code AS Agency_ID,
    NULL::VARCHAR AS ServiceURI,   -- real SIP/HTTP URI comes from the PSAP or state; never invent one
    CASE b.Agency_Type
        WHEN 'FIRE' THEN 2
        WHEN 'LAW' THEN 3
    END AS ServiceURN_ID,
    b.ServiceNum,
    NULL::VARCHAR AS AVcard_URI,   -- same: provided by the agency
    b.Agency_Name AS DsplayNam
FROM boundaries b
LEFT JOIN agencies ag
  ON b.DisclID = ag.DiscrpAgID
LEFT JOIN {{ ref('stg_source_dates') }} d
  ON d.source = CASE b.Agency_Type WHEN 'LAW' THEN 'Fresno CAD law dispatch' WHEN 'FIRE' THEN 'Fresno fire districts' END
-- City limits are an A3 admin boundary (mart_nena3_a3boundary), not a service area.
-- urn:service:sos is reserved for the PSAP boundary, which needs an authoritative PSAP layer.
WHERE b.Agency_Type IN ('LAW', 'FIRE')
