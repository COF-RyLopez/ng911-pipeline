{{ config(materialized='table') }}

-- Product 2: per city, how the county's city limits compare with CDTFA's (the state geoportal layer).
-- ponytail: status thresholds are on overlap ratio (IoU); add an absolute-area rule if small cities
-- with big relative but tiny absolute differences turn out to be noise.
SELECT
    '{{ county("label") }}' AS Jurisdiction,
    coalesce(state_city, local_city) AS City,
    state_city AS StateName,
    local_city AS LocalName,
    round(coalesce({{ area_km2('state_geom') }}, 0), 3) AS StateAreaKm2,
    round(coalesce({{ area_km2('local_geom') }}, 0), 3) AS LocalAreaKm2,
    round(overlap_km2, 3) AS OverlapKm2,
    round(StateAreaKm2 - OverlapKm2, 3) AS OnlyInStateKm2,
    round(LocalAreaKm2 - OverlapKm2, 3) AS OnlyInLocalKm2,
    round(100.0 * OverlapKm2 / nullif(StateAreaKm2 + LocalAreaKm2 - OverlapKm2, 0), 2) AS PctAgreement,
    CASE
        WHEN NOT {{ 'TRUE' if county('boundary_layers') else 'FALSE' }} THEN 'NO_LOCAL_LAYER'
        WHEN local_city IS NULL THEN 'MISSING_LOCALLY'
        WHEN state_city IS NULL THEN 'MISSING_IN_STATE'
        WHEN PctAgreement >= 99.5 THEN 'MATCH'
        WHEN PctAgreement >= 95 THEN 'MINOR_DIFFERENCES'
        ELSE 'MAJOR_DIFFERENCES'
    END AS Status
FROM {{ ref('int_boundary_pairs') }}
