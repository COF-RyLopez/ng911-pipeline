{{ config(
    materialized='table'
) }}

-- NENA v3.0 Relational Data Model: ng911.CompleteStNam
WITH names_from_addresses AS (
    SELECT DISTINCT
        pre_directional AS St_PreDir,
        street_name AS St_Name,
        street_type AS St_Typ,
        post_directional AS St_PosDir
    FROM {{ ref('stg_regional_addresses') }}
    WHERE street_name IS NOT NULL
),

names_from_streets AS (
    SELECT DISTINCT
        pre_directional AS St_PreDir,
        street_name AS St_Name,
        street_type AS St_Typ,
        post_directional AS St_PosDir
    FROM {{ ref('stg_county_streets') }}
    WHERE street_name IS NOT NULL
),

all_names AS (
    SELECT * FROM names_from_addresses
    UNION
    SELECT * FROM names_from_streets
)

SELECT
    row_number() OVER (ORDER BY St_Name, St_Typ, St_PreDir) AS CompleteStNam_ID,
    St_PreDir,
    St_Name,
    St_Typ,
    St_PosDir,
    concat_ws(' ', St_PreDir, St_Name, St_Typ, St_PosDir) AS FullStreetName
FROM all_names
