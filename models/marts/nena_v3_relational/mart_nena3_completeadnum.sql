{{ config(
    materialized='table'
) }}

-- NENA v3.0 Relational Data Model: ng911.CompleteAdNum
WITH distinct_numbers AS (
    SELECT DISTINCT
        TRY_CAST(regexp_extract(house_number, '^[0-9]+') AS INTEGER) AS Add_Number,
        house_number_suffix AS AddNum_Suf
    FROM {{ ref('stg_regional_addresses') }}
    WHERE house_number IS NOT NULL
)

SELECT
    row_number() OVER (ORDER BY Add_Number, AddNum_Suf) AS CompleteAdNum_ID,
    Add_Number,
    AddNum_Suf,
    trim(coalesce(cast(Add_Number as VARCHAR), '') || ' ' || coalesce(AddNum_Suf, '')) AS CompleteAdNum
FROM distinct_numbers
WHERE Add_Number IS NOT NULL
