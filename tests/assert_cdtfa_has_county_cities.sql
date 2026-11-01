-- Every registered county has incorporated cities in CDTFA; none means the fetch or the name filter broke.
SELECT 1
FROM (SELECT count(*) AS n FROM {{ ref('stg_cdtfa_boundaries') }} WHERE kind = 'CITY' AND county = '{{ county("name") }}')
WHERE n = 0
