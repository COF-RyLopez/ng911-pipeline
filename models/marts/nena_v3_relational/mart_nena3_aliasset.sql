{{ config(materialized='table') }}

-- NENA v3.0 Relational Data Model: ng911.AliasSet
-- ID 0 is the empty set, used by street segments with no alias names (StSeg.AliasSet_ID is required).
SELECT 0::BIGINT AS ID
UNION ALL
SELECT DISTINCT AliasSet_ID::BIGINT FROM {{ ref('int_alias_sets') }}
