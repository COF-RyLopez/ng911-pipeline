{{ config(
    materialized='table'
) }}

WITH addresses AS (
    SELECT
        CountyLocalID,
        SSAP_NGUID,
        GERS_ID,
        ConflationStatus,
        HNO,
        HNS,
        PRD,
        STN,
        STS,
        POD,
        Unit,
        Muni,
        CommunityName,
        County,
        State,
        PostCode,
        PSAP,
        PSAP_Phone,
        ESB_Fire,
        LandmarkName,
        Longitude AS enhanced_lon,
        Latitude AS enhanced_lat,
        ST_Geometry AS enhanced_geom
    FROM {{ ref('mart_ng911_addresses') }}
),

raw_inputs AS (
    SELECT
        county_id,
        house_number AS raw_hno,
        street_name AS raw_stn,
        street_type AS raw_sts,
        longitude AS raw_lon,
        latitude AS raw_lat,
        geom AS raw_geom
    FROM {{ ref('stg_county_addresses') }}
),

buildings AS (
    SELECT building_id, geom FROM {{ ref('stg_overture_buildings') }}
),

building_intersection AS (
    SELECT 
        a.SSAP_NGUID,
        min(b.building_id) AS building_id
    FROM addresses a
    JOIN buildings b 
      ON ST_Intersects(a.enhanced_geom, b.geom)
    GROUP BY a.SSAP_NGUID
),

fishbones AS (
    SELECT 
        SSAP_NGUID, 
        RCL_NGUID,
        DistanceMeters, 
        IsExcessiveOffset, 
        IsRangeViolation,
        RoadSide,
        IsWrongSide,
        ROW_NUMBER() OVER (PARTITION BY SSAP_NGUID ORDER BY DistanceMeters ASC) AS rn
    FROM {{ ref('mart_ng911_qa_fishbones') }}
),

-- Street-level imagery within ~50 m (0.0005 deg), so reviewers can start with points they can verify
street_imagery AS (
    SELECT
        a.SSAP_NGUID,
        max(s.captured_at) AS latest_capture,
        bool_or(s.is_pano) AS has_pano
    FROM addresses a
    JOIN {{ ref('stg_mapillary_sequences') }} s
      ON ST_DWithin(a.enhanced_geom, s.geom, 0.0005)
    GROUP BY a.SSAP_NGUID
),

discrepancies AS (
    SELECT
        CountyFeatureID,
        DiscrepancyType,
        Severity,
        Description,
        ROW_NUMBER() OVER (
            PARTITION BY CountyFeatureID 
            ORDER BY CASE 
                WHEN Severity = 'CRITICAL' THEN 1
                WHEN Severity = 'HIGH' THEN 2
                WHEN Severity = 'MEDIUM' THEN 3
                ELSE 4
            END ASC
        ) AS rn
    FROM {{ ref('mart_ng911_qa_discrepancies') }}
    WHERE DiscrepancyType <> 'EXCESSIVE_OFFSET_DISCREPANCY'  -- handled below with the footprint check
)

SELECT
    a.SSAP_NGUID,
    a.CountyLocalID,
    r.raw_hno AS OriginalHouseNumber,
    r.raw_stn AS OriginalStreetName,
    a.HNO || ' ' || a.STN || coalesce(' ' || a.STS, '') || coalesce(' UNIT ' || nullif(trim(a.Unit), ''), '') AS StandardizedAddress,
    a.HNO,
    a.HNS,
    a.PRD,
    a.STN,
    a.STS,
    a.POD,
    a.Unit,
    a.Muni,
    a.CommunityName,
    a.PostCode,
    r.raw_lon AS CurrentLongitude,
    r.raw_lat AS CurrentLatitude,
    a.enhanced_lon AS RemediatedLongitude,
    a.enhanced_lat AS RemediatedLatitude,
    round(f.DistanceMeters, 1) AS SpatialOffsetMeters,

    CASE
        WHEN bi.building_id IS NOT NULL THEN 'INSIDE_BUILDING_FOOTPRINT'
        ELSE 'OUTSIDE_BUILDING_FOOTPRINT'
    END AS BuildingFootprintStatus,

    a.GERS_ID AS OvertureAddressGERS_ID,
    bi.building_id AS OvertureBuildingGERS_ID,
    f.RCL_NGUID AS RoadCenterlineNGUID,
    coalesce(f.IsExcessiveOffset, TRUE) AS IsExcessiveOffset,
    coalesce(f.IsRangeViolation, FALSE) AS IsRangeViolation,
    f.RoadSide,
    coalesce(f.IsWrongSide, FALSE) AS IsWrongSide,

    CASE
        WHEN f.DistanceMeters IS NULL THEN 'UNRESOLVED_ROAD_CENTERLINE'
        WHEN f.IsWrongSide THEN 'WRONG_SIDE_OF_ROAD'
        WHEN f.IsRangeViolation = TRUE THEN 'ADDRESS_RANGE_VIOLATION'
        WHEN d.Severity IN ('CRITICAL', 'HIGH') THEN d.DiscrepancyType
        WHEN f.IsExcessiveOffset AND bi.building_id IS NULL THEN 'EXCESSIVE_OFFSET'
        WHEN bi.building_id IS NULL THEN 'OUTSIDE_BUILDING_FOOTPRINT'
        WHEN d.DiscrepancyType IS NOT NULL THEN d.DiscrepancyType
        ELSE 'NONE'
    END AS DiscrepancyType,

    CASE
        WHEN f.DistanceMeters IS NULL THEN 'CRITICAL'
        WHEN f.IsWrongSide THEN 'HIGH'
        WHEN f.IsRangeViolation = TRUE THEN 'HIGH'
        WHEN d.Severity IN ('CRITICAL', 'HIGH') THEN d.Severity
        WHEN f.IsExcessiveOffset AND bi.building_id IS NULL THEN 'MEDIUM'
        WHEN bi.building_id IS NULL THEN 'MEDIUM'
        WHEN d.Severity IS NOT NULL THEN d.Severity
        ELSE 'OK'
    END AS Severity,

    CASE
        WHEN f.DistanceMeters IS NULL THEN 'CRITICAL_ATTENTION'
        WHEN f.IsWrongSide THEN 'CRITICAL_ATTENTION'
        WHEN f.IsRangeViolation = TRUE THEN 'CRITICAL_ATTENTION'
        WHEN d.Severity IN ('CRITICAL', 'HIGH') THEN 'CRITICAL_ATTENTION'
        WHEN bi.building_id IS NULL THEN 'ATTENTION_REQUIRED'
        WHEN d.DiscrepancyType IS NOT NULL THEN 'ATTENTION_REQUIRED'
        ELSE 'VALIDATED_OK'
    END AS SymbologyCategory,

    a.PSAP,
    a.PSAP_Phone,
    a.ESB_Fire,
    a.LandmarkName,

    si.SSAP_NGUID IS NOT NULL AS HasStreetImagery,
    cast(si.latest_capture AS DATE) AS StreetImageryDate,
    coalesce(si.has_pano, FALSE) AS StreetImageryPano,

    -- Mapillary Street-Level View direct URL at address location for ground-truth verification
    'https://www.mapillary.com/app/?lat=' || cast(a.enhanced_lat as varchar) || '&lng=' || cast(a.enhanced_lon as varchar) || '&z=18' AS MapillaryGroundTruthURL,

    -- Actionable Fix Guidance for Jurisdiction GIS Analysts
    CASE
        WHEN f.DistanceMeters IS NULL THEN 'Address point failed to resolve to named road centerline within 400m; verify street name and spatial alignment'
        WHEN f.IsWrongSide THEN 'House number is odd/even opposite to the side of the road it sits on; check the number or move the point to the correct side'
        WHEN f.IsRangeViolation = TRUE THEN 'House number is outside the address range of its side of the road segment'
        WHEN d.DiscrepancyType = 'CIVIC_ADDRESS_AMBIGUITY' THEN 'Another point has this same complete address (including unit); remove the duplicate or assign distinct unit numbers'
        WHEN f.IsExcessiveOffset AND bi.building_id IS NULL THEN 'Over 50 m from the road centerline and not inside a building; move a structure point into its building, or a driveway point to where the driveway meets the road'
        WHEN bi.building_id IS NULL THEN 'Address point is outside building footprint; inspect aerial/Mapillary imagery to verify placement'
        WHEN a.PSAP IS NULL THEN 'Verify municipal boundary for PSAP dispatch assignment'
        ELSE 'Validated OK against building footprint & road centerline'
    END AS RecommendedRemediationAction,

    -- lineage: the source Overture republished for the matched address (for Fresno, the county's own
    -- layer via OpenAddresses), so the county can see that fixing its data fixes Overture's copy
    ov.source_dataset AS OvertureSourceDataset,
    {{ oa_source_url('ov.source_dataset') }} AS OvertureSourceUrl,
    a.enhanced_geom AS ST_Geometry

FROM addresses a
INNER JOIN raw_inputs r ON a.CountyLocalID = r.county_id
LEFT JOIN building_intersection bi ON a.SSAP_NGUID = bi.SSAP_NGUID
LEFT JOIN street_imagery si ON a.SSAP_NGUID = si.SSAP_NGUID
LEFT JOIN fishbones f ON a.SSAP_NGUID = f.SSAP_NGUID AND f.rn = 1
LEFT JOIN discrepancies d ON (a.CountyLocalID = d.CountyFeatureID OR a.SSAP_NGUID = d.CountyFeatureID) AND d.rn = 1
LEFT JOIN {{ ref('stg_overture_addresses') }} ov ON ov.overture_id = a.GERS_ID

-- Source address points (county data republished via OpenAddresses/Overture) that have a house number
-- but no street. They cannot be SSAPs, so the pipeline drops them; list them here for the county to complete.
UNION ALL BY NAME
SELECT
    'urn:emergency:uid:gis:SSAP:' || o.overture_id || ':{{ county("agency_domain") }}' AS SSAP_NGUID,
    o.house_number AS OriginalHouseNumber,
    o.house_number AS HNO,
    o.community_name AS CommunityName,
    o.postcode AS PostCode,
    o.longitude AS CurrentLongitude,
    o.latitude AS CurrentLatitude,
    'NOT_CHECKED' AS BuildingFootprintStatus,
    o.overture_id AS OvertureAddressGERS_ID,
    FALSE AS IsExcessiveOffset,
    FALSE AS IsRangeViolation,
    FALSE AS IsWrongSide,
    'MISSING_STREET_NAME' AS DiscrepancyType,
    'CRITICAL' AS Severity,
    'CRITICAL_ATTENTION' AS SymbologyCategory,
    FALSE AS HasStreetImagery,
    FALSE AS StreetImageryPano,
    'https://www.mapillary.com/app/?lat=' || cast(o.latitude AS VARCHAR) || '&lng=' || cast(o.longitude AS VARCHAR) || '&z=18' AS MapillaryGroundTruthURL,
    'Address point has a house number but no street name; add the street so it can be dispatched' AS RecommendedRemediationAction,
    o.source_dataset AS OvertureSourceDataset,
    {{ oa_source_url('o.source_dataset') }} AS OvertureSourceUrl,
    ST_GeomFromWKB(ST_AsWKB(o.geom)) AS ST_Geometry
FROM {{ ref('stg_overture_addresses') }} o
CROSS JOIN {{ ref('oo_county_boundary') }} c
WHERE o.street_name IS NULL
  AND ST_Within(ST_GeomFromWKB(ST_AsWKB(o.geom)), c.geom)
