-- Reconciled cities must not overlap (NENA boundaries: no overlaps between agencies). 1 ha tolerance.
SELECT a.City, b.City
FROM {{ ref('mart_reconciled_city_boundaries') }} a
JOIN {{ ref('mart_reconciled_city_boundaries') }} b
  ON a.City < b.City AND ST_Intersects(a.ST_Geometry, b.ST_Geometry)
WHERE {{ area_km2('ST_Intersection(a.ST_Geometry, b.ST_Geometry)') }} > 0.01
