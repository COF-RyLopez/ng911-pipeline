#!/usr/bin/env python3
"""
scripts/generate_comparison_geolibre_project.py

Generates the 1-click GeoLibre Comparison, QA/QC & Actionable Remediation project files
(.geolibre and .geolibre.json) for raw source vs NG911 enhanced datasets.

Features:
- NENA Road Centerlines (RCL) vector layer
- QA/QC Spatial Displacement Vectors & Fishbones (snapping distance lines)
- Color-coded rule-violation & building footprint remediation symbology:
    * Red (#dc2626): CRITICAL_POS_OFFSET / Missing mandatory NENA fields
    * Orange (#ea580c): OUTSIDE_BUILDING_FOOTPRINT
    * Yellow (#eab308): MISSING_NENA_MANDATORY_FIELD
    * Green (#16a34a): VALIDATED_OK
- Direct interactive Mapillary ground-truth street-level view links in feature popups.
- GeoLibre plugins integration: swipe, geo-editor, dimensions, mapillary.
"""

import argparse
import json
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

GITHUB_BASE_URL = "https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output"
TILES_BASE_URL = f"{GITHUB_BASE_URL}/tiles"


def load_geojson(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"type": "FeatureCollection", "features": []}


def pmtiles_layer(layer_id, name, filename, source_layer, style, popup, opacity=1.0):
    url = f"{TILES_BASE_URL}/{filename}"
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


def main():
    parser = argparse.ArgumentParser(description="Generate GeoLibre QA/QC Comparison Project.")
    parser.add_argument("--source-file", help="Path to local user source dataset (.geojson, .parquet, .csv)", default=None)
    args = parser.parse_args()

    remediation_geojson = load_geojson("remediation/county_remediation_points_sample.geojson")
    fishbones_geojson = load_geojson("mart_ng911_fresno_fishbones_sample.geojson")
    rcl_geojson = load_geojson("mart_ng911_fresno_rcl_sample.geojson")

    project_data = {
        "version": "0.1.0",
        "name": "NG911 Address Enhancement & Actionable Jurisdiction Remediation Hub",
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
            "zoom": 14,
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
                "name": "Authoritative NENA Road Centerlines (Sample)",
                "type": "geojson",
                "visible": True,
                "opacity": 0.85,
                "geojson": rcl_geojson,
                "source": {
                    "type": "geojson",
                    "url": f"{GITHUB_BASE_URL}/mart_ng911_fresno_rcl_sample.geojson"
                },
                "sourcePath": f"{GITHUB_BASE_URL}/mart_ng911_fresno_rcl_sample.geojson",
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
                "Authoritative NENA Road Centerlines (All 53,474)",
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
                }
            ),
            {
                "id": "mart_ng911_fresno_fishbones_geojson",
                "name": "QA/QC Spatial Displacement Vectors & Fishbones (Sample)",
                "type": "geojson",
                "visible": True,
                "opacity": 0.9,
                "geojson": fishbones_geojson,
                "source": {
                    "type": "geojson",
                    "url": f"{GITHUB_BASE_URL}/mart_ng911_fresno_fishbones_sample.geojson"
                },
                "sourcePath": f"{GITHUB_BASE_URL}/mart_ng911_fresno_fishbones_sample.geojson",
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
                "QA/QC Spatial Displacement Vectors & Fishbones (All 365,316)",
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
                }
            ),
            {
                "id": "mart_ng911_county_remediation_geojson",
                "name": "NG911 Rule Violation & Remediation Symbology (Sample)",
                "type": "geojson",
                "visible": True,
                "opacity": 1.0,
                "geojson": remediation_geojson,
                "source": {
                    "type": "geojson",
                    "url": f"{GITHUB_BASE_URL}/remediation/county_remediation_points_sample.geojson"
                },
                "sourcePath": f"{GITHUB_BASE_URL}/remediation/county_remediation_points_sample.geojson",
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
                "NG911 Rule Violation & Remediation Symbology (All 395,000)",
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
                }
            )
        ]
    }

    json_path = os.path.join(OUTPUT_DIR, "ng911_address_comparison.geolibre.json")
    proj_path = os.path.join(OUTPUT_DIR, "ng911_address_comparison.geolibre")

    with open(json_path, "w") as f:
        json.dump(project_data, f, indent=2)

    with open(proj_path, "w") as f:
        json.dump(project_data, f, indent=2)

    print(f"Generated GeoLibre QA/QC Comparison Project:\n  -> {json_path}\n  -> {proj_path}")


if __name__ == "__main__":
    main()
