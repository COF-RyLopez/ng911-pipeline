-- Mart: mart_esri_adm_masterroadname
-- Esri Address Data Management (ADM 2.5) MasterRoadName table: one row per distinct road name on the
-- centerlines, so ADM's attribute rules accept the centerline and site address fullname values.
-- roadtype uses the RoadType domain's casing ('Ave', 'Blvd'); the pipeline stores USPS upper case.

{{ config(materialized='table') }}

SELECT DISTINCT
    NULL::VARCHAR AS roadpremod,
    nullif(St_PreDir, '') AS roadpredir,
    NULL::VARCHAR AS roadpretype,
    NULL::VARCHAR AS roadpretypesep,
    St_Name AS roadname,
    CASE WHEN nullif(St_Typ, '') IS NOT NULL THEN upper(left(St_Typ, 1)) || lower(substr(St_Typ, 2)) END AS roadtype,
    nullif(St_PosDir, '') AS roadpostdir,
    NULL::VARCHAR AS roadpostmod,
    FullStreetName AS fullname,
    NULL::VARCHAR AS municipality,
    'Current' AS status
FROM {{ ref('mart_ng911_road_centerlines') }}
WHERE FullStreetName IS NOT NULL
