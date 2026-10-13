{{ config(materialized='table') }}

-- NENA v3.0 Relational Data Model: ng911.Alias (AliasSet -> CompleteStNam membership)
SELECT
    row_number() OVER (ORDER BY AliasSet_ID, CompleteStNam_ID)::BIGINT AS ID,
    AliasSet_ID::BIGINT AS AliasSet_ID,
    CompleteStNam_ID::BIGINT AS CompleteStNam_ID
FROM (SELECT DISTINCT AliasSet_ID, CompleteStNam_ID FROM {{ ref('int_alias_sets') }})
