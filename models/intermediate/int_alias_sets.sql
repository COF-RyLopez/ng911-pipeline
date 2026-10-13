{{ config(materialized='table') }}

-- Segment -> NENA AliasSet. Segments with the same set of alias names share one AliasSet,
-- so e.g. every segment also known as HIGHWAY 43 points to the same set.
WITH alias_ids AS (
    SELECT DISTINCT a.street_segment_id, cs.CompleteStNam_ID
    FROM {{ ref('int_street_aliases') }} a
    JOIN {{ ref('mart_nena3_completestnam') }} cs
      ON coalesce(a.pre_directional, '') = coalesce(cs.St_PreDir, '')
     AND a.street_name = cs.St_Name
     AND coalesce(a.street_type, '') = coalesce(cs.St_Typ, '')
     AND coalesce(a.post_directional, '') = coalesce(cs.St_PosDir, '')
),
keyed AS (
    SELECT street_segment_id, string_agg(CompleteStNam_ID::VARCHAR, ',' ORDER BY CompleteStNam_ID) AS set_key
    FROM alias_ids GROUP BY 1
)
SELECT k.street_segment_id, dense_rank() OVER (ORDER BY k.set_key) AS AliasSet_ID, a.CompleteStNam_ID
FROM keyed k JOIN alias_ids a USING (street_segment_id)
