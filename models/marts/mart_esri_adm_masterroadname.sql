-- Mart: mart_esri_adm_masterroadname
-- Esri Address Data Management (ADM 2.5) MasterRoadName table: one row per distinct road name on the
-- centerlines, so ADM's attribute rules accept the centerline and site address fullname values.
-- roadtype uses the RoadType domain's casing ('Ave', 'Blvd'); the pipeline stores USPS upper case.
-- ponytail: tokens that sit in the type slot but are not street types (ramp ON/OFF, SR, local codes,
-- found in the Oct 2026 data) move back into roadname; the roadtype warn test flags any new ones.

{{ config(materialized='table') }}

WITH names AS (
    SELECT *, upper(St_Typ) IN ('ON', 'OFF', 'SR', 'GRD', 'FTRD', 'BKRT') AS type_is_name
    FROM {{ ref('mart_ng911_road_centerlines') }}
    WHERE FullStreetName IS NOT NULL
)

SELECT DISTINCT
    NULL::VARCHAR AS roadpremod,
    nullif(St_PreDir, '') AS roadpredir,
    NULL::VARCHAR AS roadpretype,
    NULL::VARCHAR AS roadpretypesep,
    CASE WHEN type_is_name THEN St_Name || ' ' || St_Typ ELSE St_Name END AS roadname,
    CASE WHEN nullif(St_Typ, '') IS NOT NULL AND NOT type_is_name
         THEN upper(left(St_Typ, 1)) || lower(substr(St_Typ, 2)) END AS roadtype,
    nullif(St_PosDir, '') AS roadpostdir,
    NULL::VARCHAR AS roadpostmod,
    FullStreetName AS fullname,
    NULL::VARCHAR AS municipality,
    'Current' AS status
FROM names
