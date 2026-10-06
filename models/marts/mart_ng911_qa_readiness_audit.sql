{{ config(
    materialized='table'
) }}

WITH addrs AS (
    SELECT 
        count(*) AS total_addresses,
        count(PSAP) AS psap_attributed,
        count(ESB_Fire) AS fire_attributed,
        count(LandmarkName) AS landmark_attributed
    FROM {{ ref('mart_ng911_addresses') }}
),

fishbones AS (
    SELECT 
        count(*) AS total_fishbones,
        count(CASE WHEN IsExcessiveOffset = FALSE THEN 1 END) AS compliant_snapped,
        count(CASE WHEN IsExcessiveOffset = TRUE THEN 1 END) AS excessive_offset_count
    FROM {{ ref('mart_ng911_qa_fishbones') }}
),

roads AS (
    SELECT 
        count(*) AS total_road_segments,
        count(CASE 
            WHEN (FromAddr_L IS NOT NULL AND ToAddr_L IS NOT NULL AND FromAddr_L > ToAddr_L)
              OR (FromAddr_R IS NOT NULL AND ToAddr_R IS NOT NULL AND FromAddr_R > ToAddr_R)
            THEN 1 
        END) AS range_inversions
    FROM {{ ref('mart_ng911_road_centerlines') }}
)

SELECT
    'Fresno County, CA' AS Jurisdiction,
    '{{ var("agency_domain", "fresnocountyca.gov") }}' AS DisclID,
    
    -- SSAP Counts & Compliance
    a.total_addresses AS Total_SSAP_Addresses,
    f.compliant_snapped AS SSAP_Snapped_Within_50m,
    round((f.compliant_snapped * 100.0) / nullif(f.total_fishbones, 0), 2) AS Pct_SSAP_Snapped_Within_50m,
    
    -- PSAP Boundary Attribution
    a.psap_attributed AS SSAP_With_PSAP,
    round((a.psap_attributed * 100.0) / nullif(a.total_addresses, 0), 2) AS Pct_PSAP_Attributed,
    
    -- Fire ESB Attribution
    a.fire_attributed AS SSAP_With_Fire_ESB,
    round((a.fire_attributed * 100.0) / nullif(a.total_addresses, 0), 2) AS Pct_Fire_Attributed,

    -- Landmark & POI Dispatch Aliasing
    a.landmark_attributed AS SSAP_With_Landmark_Alias,
    
    -- RCL Topology & Range Validation
    r.total_road_segments AS Total_Road_Segments,
    r.range_inversions AS Road_Range_Inversions,

    -- Cal OES 98% Readiness Gates
    CASE 
        WHEN round((f.compliant_snapped * 100.0) / nullif(f.total_fishbones, 0), 2) >= 98.0 
        THEN TRUE ELSE FALSE 
    END AS Snapping_Threshold_Passed,

    CASE 
        WHEN round((a.psap_attributed * 100.0) / nullif(a.total_addresses, 0), 2) >= 98.0 
        THEN TRUE ELSE FALSE 
    END AS PSAP_Coverage_Passed,

    CASE 
        WHEN r.range_inversions = 0 
        THEN TRUE ELSE FALSE 
    END AS Zero_Range_Inversions_Passed,

    -- Composite Statewide NG911 Transition Verdict
    CASE 
        WHEN (f.compliant_snapped * 100.0 / nullif(f.total_fishbones, 0) >= 98.0)
         AND (a.psap_attributed * 100.0 / nullif(a.total_addresses, 0) >= 98.0)
         AND (r.range_inversions = 0)
        THEN 'PASSED_CAL_OES_98_PERCENT_READY'
        ELSE 'ACTION_REQUIRED_DEFICIENT'
    END AS Cal_OES_Readiness_Status,

    current_timestamp AS Audit_Timestamp

FROM addrs a
CROSS JOIN fishbones f
CROSS JOIN roads r
