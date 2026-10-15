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

    -- Mapillary Street-Level View direct URL at address location for ground-truth verification
    'https://www.mapillary.com/app/?lat=' || cast(a.enhanced_lat as varchar) || '&lng=' || cast(a.enhanced_lon as varchar) || '&z=18' AS MapillaryGroundTruthURL,

    -- Actionable Fix Guidance for Jurisdiction GIS Analysts
    CASE
        WHEN f.DistanceMeters IS NULL THEN 'Address point failed to resolve to named road centerline within 200m; verify street name and spatial alignment'
        WHEN f.IsWrongSide THEN 'House number is odd/even opposite to the side of the road it sits on; check the number or move the point to the correct side'
        WHEN f.IsRangeViolation = TRUE THEN 'House number is outside the address range of its side of the road segment'
        WHEN d.DiscrepancyType = 'CIVIC_ADDRESS_AMBIGUITY' THEN 'Another point has this same complete address (including unit); remove the duplicate or assign distinct unit numbers'
        WHEN f.IsExcessiveOffset AND bi.building_id IS NULL THEN 'Over 50 m from the road centerline and not inside a building; move a structure point into its building, or a driveway point to where the driveway meets the road'
        WHEN bi.building_id IS NULL THEN 'Address point is outside building footprint; inspect aerial/Mapillary imagery to verify placement'
        WHEN a.PSAP IS NULL THEN 'Verify municipal boundary for PSAP dispatch assignment'
        ELSE 'Validated OK against building footprint & road centerline'
    END AS RecommendedRemediationAction,

    a.enhanced_geom AS ST_Geometry

FROM addresses a
INNER JOIN raw_inputs r ON a.CountyLocalID = r.county_id
LEFT JOIN building_intersection bi ON a.SSAP_NGUID = bi.SSAP_NGUID
LEFT JOIN fishbones f ON a.SSAP_NGUID = f.SSAP_NGUID AND f.rn = 1
LEFT JOIN discrepancies d ON (a.CountyLocalID = d.CountyFeatureID OR a.SSAP_NGUID = d.CountyFeatureID) AND d.rn = 1
