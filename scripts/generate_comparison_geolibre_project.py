#!/usr/bin/env python3
"""
scripts/generate_comparison_geolibre_project.py

Generates 1-click GeoLibre Comparison, QA/QC & Actionable Remediation project files
(.geolibre and .geolibre.json) for raw source vs NG911 enhanced datasets.

Features:
- Lightweight project configuration (<50 KB) preventing GeoLibre autosave snapshot limit errors (>10 MB).
- Streams vectors dynamically via URL endpoints.
"""

import argparse
import json
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

GITHUB_PAGES_BASE_URL = "https://cof-rylopez.github.io/ng911-pipeline/data/output"
GITHUB_RAW_BASE_URL = "https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output"
LOCAL_BASE_URL = "http://localhost:8088"


def pmtiles_layer(layer_id, name, filename, source_layer, style, popup, base_url, opacity=1.0):
    url = f"{base_url}/tiles/{filename}"
    return {
        "id": layer_id,
        "name": name,
        "type": "pmtiles",
        "visible": True,
        "opacity": opacity,
        "source": {
            "type": "vector",
            "url": url,
            "sourceId": layer_id,
            "sourceLayers": [source_layer],
            "tileType": "vector",
        },
        "sourcePath": url,
        "style": {"minZoom": 0, "maxZoom": 24, **style},
        "metadata": {
            "sourceKind": "pmtiles-url",
            "externalNativeLayer": True,
            "pickable": True,
            "sourceId": layer_id,
            "tileType": "vector",
            "sourceLayers": [source_layer],
            "nativeLayerIds": [layer_id],
        },
        "popup": popup,
    }


def build_project(base_url, is_local=False):
    raw_base = GITHUB_RAW_BASE_URL if not is_local else LOCAL_BASE_URL

    return {
        "version": "0.1.0",
        "name": f"NG911 Address Enhancement & Remediation Hub {'(Local Server)' if is_local else '(Cloud Remote)'}",
        "metadata": {
            "author": "County of Fresno (Ryan Lopez) & Cal OES GIS Committee",
            "jurisdiction": "County of Fresno, California (FIPS 06019)",
            "repository": "https://github.com/COF-RyLopez/ng911-pipeline",
            "standard": "NENA-STA-010-2021 & Cal OES NG911 GIS Guidelines",
            "description": "Interactive visual QA/QC and remediation hub comparing raw local address points against NG911 remediated address points, showing rule-violation symbology, building footprint intersections, spatial displacement vectors, and Mapillary street views.",
            "plugins": ["swipe", "geo-editor", "dimensions", "mapillary"]
        },
        "mapView": {
            "center": [-119.7871, 36.7468],
            "zoom": 15,
            "bearing": 0,
            "pitch": 0,
            "bbox": [-119.95, 36.65, -119.65, 36.90]
        },
        "basemapStyleUrl": "https://tiles.openfreemap.org/styles/positron",
        "basemapVisible": True,
        "basemapOpacity": 1.0,
        "primaryRenderer": "maplibre",
        "layers": [
            {
                "id": "mart_ng911_fresno_rcl_geojson",
                "name": "Authoritative NENA Road Centerlines (25,000 Vectors)",
                "type": "geojson",
                "visible": True,
                "opacity": 0.85,
                "source": {
                    "type": "geojson",
                    "url": f"{raw_base}/mart_ng911_fresno_rcl_sample.geojson"
                },
                "sourcePath": f"{raw_base}/mart_ng911_fresno_rcl_sample.geojson",
                "style": {
                    "fillColor": "#059669",
                    "strokeColor": "#059669",
                    "strokeWidth": 2.5,
                    "strokeWidthUnit": "pixels",
                    "minZoom": 0,
                    "maxZoom": 24
                },
                "popup": {
                    "click": True,
                    "hover": True,
                    "titleField": "FullStreetName",
                    "fields": [
                        {"field": "FullStreetName", "label": "Street Name", "hover": True},
                        {"field": "FromAddr_L", "label": "From Left"},
                        {"field": "ToAddr_L", "label": "To Left"},
                        {"field": "FromAddr_R", "label": "From Right"},
                        {"field": "ToAddr_R", "label": "To Right"},
                        {"field": "RoadClass", "label": "Road Class"},
                        {"field": "RCL_NGUID", "label": "NENA RCL NGUID"}
                    ]
                }
            },
            pmtiles_layer(
                "mart_ng911_fresno_rcl_tiles",
                "Authoritative NENA Road Centerlines (Full 53,474)",
                "fresno_rcl.pmtiles",
                "rcl",
                {
                    "fillColor": "#059669",
                    "strokeColor": "#059669",
                    "strokeWidth": 2.0,
                    "strokeWidthUnit": "pixels"
                },
                {
                    "click": True,
                    "hover": True,
                    "titleField": "FullStreetName",
                    "fields": [
                        {"field": "FullStreetName", "label": "Street Name", "hover": True},
                        {"field": "FromAddr_L", "label": "From Left"},
                        {"field": "ToAddr_L", "label": "To Left"},
                        {"field": "FromAddr_R", "label": "From Right"},
                        {"field": "ToAddr_R", "label": "To Right"},
                        {"field": "RoadClass", "label": "Road Class"},
                        {"field": "RCL_NGUID", "label": "NENA RCL NGUID"}
                    ]
                },
                base_url
            ),
            {
                "id": "mart_ng911_fresno_fishbones_geojson",
                "name": "QA/QC Displacement Vectors & Fishbones (25,000 Vectors)",
                "type": "geojson",
                "visible": True,
                "opacity": 0.9,
                "source": {
                    "type": "geojson",
                    "url": f"{raw_base}/mart_ng911_fresno_fishbones_sample.geojson"
                },
                "sourcePath": f"{raw_base}/mart_ng911_fresno_fishbones_sample.geojson",
                "style": {
                    "fillColor": "#dc2626",
                    "strokeColor": "#dc2626",
                    "strokeWidth": 2.0,
                    "strokeWidthUnit": "pixels",
                    "minZoom": 0,
                    "maxZoom": 24
                },
                "popup": {
                    "click": True,
                    "hover": True,
                    "titleField": "STN",
                    "fields": [
                        {"field": "HNO", "label": "House Number", "hover": True},
                        {"field": "STN", "label": "Street Name", "hover": True},
                        {"field": "DistanceMeters", "label": "Displacement / Offset (m)", "kind": "number", "format": {"decimals": 1, "suffix": " m"}, "hover": True},
                        {"field": "IsExcessiveOffset", "label": "Excessive Offset (>50m)"},
                        {"field": "IsRangeViolation", "label": "Range Violation"},
                        {"field": "FishboneID", "label": "NENA Fishbone URN"}
                    ]
                }
            },
            pmtiles_layer(
                "mart_ng911_fresno_fishbones_tiles",
                "QA/QC Displacement Vectors & Fishbones (Full 365,316)",
                "fresno_fishbones.pmtiles",
                "fishbones",
                {
                    "fillColor": "#dc2626",
                    "strokeColor": "#dc2626",
                    "strokeWidth": 1.5,
                    "strokeWidthUnit": "pixels"
                },
                {
                    "click": True,
                    "hover": True,
                    "titleField": "STN",
                    "fields": [
                        {"field": "HNO", "label": "House Number", "hover": True},
                        {"field": "STN", "label": "Street Name", "hover": True},
                        {"field": "DistanceMeters", "label": "Displacement / Offset (m)", "kind": "number", "format": {"decimals": 1, "suffix": " m"}, "hover": True},
                        {"field": "IsExcessiveOffset", "label": "Excessive Offset (>50m)"},
                        {"field": "IsRangeViolation", "label": "Range Violation"},
                        {"field": "FishboneID", "label": "NENA Fishbone URN"}
                    ]
                },
                base_url
            ),
            {
                "id": "mart_ng911_county_remediation_geojson",
                "name": "NG911 Rule Violation & Remediation Symbology (Action Items)",
                "type": "geojson",
                "visible": True,
                "opacity": 1.0,
                "source": {
                    "type": "geojson",
                    "url": f"{raw_base}/remediation/county_remediation_points_sample.geojson"
                },
                "sourcePath": f"{raw_base}/remediation/county_remediation_points_sample.geojson",
                "style": {
                    "circleRadius": 7,
                    "fillColor": [
                        "match",
                        ["get", "SymbologyCategory"],
                        "CRITICAL_POS_OFFSET", "#dc2626",
                        "OUTSIDE_BUILDING_FOOTPRINT", "#ea580c",
                        "MISSING_NENA_MANDATORY_FIELD", "#eab308",
                        "VALIDATED_OK", "#16a34a",
                        "#3b82f6"
                    ],
                    "strokeColor": "#ffffff",
                    "strokeWidth": 1.5,
                    "minZoom": 0,
                    "maxZoom": 24
                },
                "popup": {
                    "click": True,
                    "hover": True,
                    "titleField": "StandardizedAddress",
                    "fields": [
                        {"field": "StandardizedAddress", "label": "Enhanced Address", "hover": True},
                        {"field": "SymbologyCategory", "label": "Rule Violation Status", "hover": True},
                        {"field": "BuildingFootprintStatus", "label": "Building Footprint Containment", "hover": True},
                        {"field": "SpatialOffsetMeters", "label": "Spatial Offset (m)", "kind": "number", "format": {"decimals": 1, "suffix": " m"}},
                        {"field": "RecommendedRemediationAction", "label": "Action Needed"},
                        {"field": "MapillaryGroundTruthURL", "label": "Mapillary Street View Link", "kind": "url"},
                        {"field": "SSAP_NGUID", "label": "NENA SSAP NGUID"}
                    ]
                }
            },
            pmtiles_layer(
                "mart_ng911_county_remediation_tiles",
                "NG911 Rule Violation & Remediation Symbology (Full 395,000)",
                "fresno_remediation.pmtiles",
                "remediation",
                {
                    "circleRadius": 6,
                    "fillColor": [
                        "match",
                        ["get", "SymbologyCategory"],
                        "CRITICAL_POS_OFFSET", "#dc2626",
                        "OUTSIDE_BUILDING_FOOTPRINT", "#ea580c",
                        "MISSING_NENA_MANDATORY_FIELD", "#eab308",
                        "VALIDATED_OK", "#16a34a",
                        "#3b82f6"
                    ],
                    "strokeColor": "#ffffff",
                    "strokeWidth": 1.5
                },
                {
                    "click": True,
                    "hover": True,
                    "titleField": "StandardizedAddress",
                    "fields": [
                        {"field": "StandardizedAddress", "label": "Enhanced Address", "hover": True},
                        {"field": "SymbologyCategory", "label": "Rule Violation Status", "hover": True},
                        {"field": "BuildingFootprintStatus", "label": "Building Footprint Containment", "hover": True},
                        {"field": "SpatialOffsetMeters", "label": "Spatial Offset (m)", "kind": "number", "format": {"decimals": 1, "suffix": " m"}},
                        {"field": "RecommendedRemediationAction", "label": "Action Needed"},
                        {"field": "MapillaryGroundTruthURL", "label": "Mapillary Street View Link", "kind": "url"},
                        {"field": "SSAP_NGUID", "label": "NENA SSAP NGUID"}
                    ]
                },
                base_url
            )
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="Generate GeoLibre QA/QC Comparison Project.")
    parser.add_argument("--source-file", help="Path to local user source dataset (.geojson, .parquet, .csv)", default=None)
    args = parser.parse_args()

    # Build Remote Project (GitHub Pages Byte Serving URL)
    remote_proj = build_project(GITHUB_PAGES_BASE_URL, is_local=False)
    json_path = os.path.join(OUTPUT_DIR, "ng911_address_comparison.geolibre.json")
    geolibre_path = os.path.join(OUTPUT_DIR, "ng911_address_comparison.geolibre")

    with open(json_path, "w") as f:
        json.dump(remote_proj, f, indent=2)

    with open(geolibre_path, "w") as f:
        json.dump(remote_proj, f, indent=2)

    # Build Local Project (http://localhost:8088/ Byte Serving URL)
    local_proj = build_project(LOCAL_BASE_URL, is_local=True)
    local_json_path = os.path.join(OUTPUT_DIR, "ng911_address_comparison_local.geolibre.json")
    local_geolibre_path = os.path.join(OUTPUT_DIR, "ng911_address_comparison_local.geolibre")

    with open(local_json_path, "w") as f:
        json.dump(local_proj, f, indent=2)

    with open(local_geolibre_path, "w") as f:
        json.dump(local_proj, f, indent=2)

    print("Generated GeoLibre QA/QC Projects (Lightweight <50 KB):")
    print(f"  Remote -> {json_path} ({os.path.getsize(json_path) / 1024:.1f} KB)")
    print(f"  Local  -> {local_json_path} ({os.path.getsize(local_json_path) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
