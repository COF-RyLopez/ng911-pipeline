#!/usr/bin/env python3
"""
scripts/generate_geolibre_project.py

Generates a fully self-contained, inline GeoLibre Project file (.geolibre and .geolibre.json)
for the Fresno County NG911 Pilot.
Includes:
- Pre-styled layers (Fishbones in high-visibility red, SSAP in blue, RCL in emerald)
- INLINE GeoJSON feature payloads (guarantees layers load instantly without external network dependency)
- Permanent public GitHub raw fallback URLs for statewide cloud streaming
- Detailed NENA attribute popup configurations
- Built-in DuckDB Dashboard charts (Fishbone offset histogram, conflation distribution)
- Default map extent centered on Fresno County metro
"""

import os
import json

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

GITHUB_BASE_URL = "https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output"

def load_sample_geojson(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"type": "FeatureCollection", "features": []}

def main():
    fb_geojson = load_sample_geojson("mart_ng911_fresno_fishbones_sample.geojson")
    ssap_geojson = load_sample_geojson("mart_ng911_fresno_ssap_sample.geojson")
    rcl_geojson = load_sample_geojson("mart_ng911_fresno_rcl_sample.geojson")

    project_data = {
        "version": "0.1.0",
        "name": "Fresno County NG911 QA/QC & Conflation Pilot",
        "metadata": {
            "author": "County of Fresno (Ryan Lopez)",
            "jurisdiction": "County of Fresno, California (FIPS 06019)",
            "repository": "https://github.com/COF-RyLopez/ng911-pipeline",
            "standard": "NENA-STA-010-2021",
            "description": "Cloud-native NG911 emergency dispatch layers with automated fishbone validation and Overture conflation."
        },
        "mapView": {
            "center": [-119.7871, 36.7468],
            "zoom": 13,
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
                "id": "mart_ng911_fresno_fishbones",
                "name": "QA/QC Fishbone Vectors (NENA Distance)",
                "type": "geojson",
                "visible": True,
                "opacity": 1.0,
                "geojson": fb_geojson,
                "source": {
                    "type": "geojson",
                    "url": f"{GITHUB_BASE_URL}/mart_ng911_fresno_fishbones_sample.geojson"
                },
                "sourcePath": f"{GITHUB_BASE_URL}/mart_ng911_fresno_fishbones_sample.geojson",
                "style": {
                    "strokeColor": "#ef4444",
                    "strokeWidth": 2.5,
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
                        {"field": "DistanceMeters", "label": "Distance to Centerline (m)", "kind": "number", "format": {"decimals": 1, "suffix": " m"}, "hover": True},
                        {"field": "IsExcessiveOffset", "label": "Excessive Offset (>50m)"},
                        {"field": "FishboneID", "label": "NENA Fishbone URN"},
                        {"field": "SSAP_NGUID", "label": "Matched SSAP Point"},
                        {"field": "RCL_NGUID", "label": "Matched Road Segment"}
                    ]
                }
            },
            {
                "id": "mart_ng911_fresno_ssap",
                "name": "NENA SSAP Address Points",
                "type": "geojson",
                "visible": True,
                "opacity": 1.0,
                "geojson": ssap_geojson,
                "source": {
                    "type": "geojson",
                    "url": f"{GITHUB_BASE_URL}/mart_ng911_fresno_ssap_sample.geojson"
                },
                "sourcePath": f"{GITHUB_BASE_URL}/mart_ng911_fresno_ssap_sample.geojson",
                "style": {
                    "circleRadius": 5,
                    "fillColor": "#2563eb",
                    "strokeColor": "#ffffff",
                    "strokeWidth": 1.5,
                    "fillOpacity": 0.85,
                    "minZoom": 0,
                    "maxZoom": 24
                },
                "popup": {
                    "click": True,
                    "hover": True,
                    "titleField": "HNO",
                    "fields": [
                        {"field": "HNO", "label": "Number", "hover": True},
                        {"field": "STN", "label": "Street", "hover": True},
                        {"field": "CommunityName", "label": "Community"},
                        {"field": "ConflationStatus", "label": "Conflation Status", "hover": True},
                        {"field": "Source", "label": "Lineage Source"},
                        {"field": "GERS_ID", "label": "Overture GERS ID"},
                        {"field": "SSAP_NGUID", "label": "NENA SSAP NGUID"}
                    ]
                }
            },
            {
                "id": "mart_ng911_fresno_rcl",
                "name": "NENA Road Centerlines (Authoritative)",
                "type": "geojson",
                "visible": True,
                "opacity": 1.0,
                "geojson": rcl_geojson,
                "source": {
                    "type": "geojson",
                    "url": f"{GITHUB_BASE_URL}/mart_ng911_fresno_rcl_sample.geojson"
                },
                "sourcePath": f"{GITHUB_BASE_URL}/mart_ng911_fresno_rcl_sample.geojson",
                "style": {
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
                        {"field": "FromAddr_L", "label": "From Left", "kind": "number"},
                        {"field": "ToAddr_L", "label": "To Left", "kind": "number"},
                        {"field": "FromAddr_R", "label": "From Right", "kind": "number"},
                        {"field": "ToAddr_R", "label": "To Right", "kind": "number"},
                        {"field": "RoadClass", "label": "Road Class"},
                        {"field": "RCL_NGUID", "label": "NENA RCL NGUID"}
                    ]
                }
            }
        ],
        "widgets": [
            {
                "id": "w_distance_hist",
                "layerId": "mart_ng911_fresno_fishbones",
                "type": "histogram",
                "field": "DistanceMeters",
                "bins": 15,
                "title": "NENA Offset Distance (Meters)",
                "color": "#ef4444"
            },
            {
                "id": "w_conflation_bar",
                "layerId": "mart_ng911_fresno_ssap",
                "type": "bar",
                "category": "ConflationStatus",
                "aggregation": "count",
                "title": "Address Conflation Breakdown",
                "color": "#2563eb"
            }
        ],
        "dashboardColumns": 2,
        "interaction": {
            "identify": ["mart_ng911_fresno_fishbones", "mart_ng911_fresno_ssap"],
            "controls": {
                "search": True,
                "measure": True,
                "navigation": True,
                "scale": True
            }
        }
    }

    proj_path_json = os.path.join(OUTPUT_DIR, "fresno_ng911_pilot.geolibre.json")
    proj_path_geolibre = os.path.join(OUTPUT_DIR, "fresno_ng911_pilot.geolibre")

    with open(proj_path_json, "w") as f:
        json.dump(project_data, f)

    with open(proj_path_geolibre, "w") as f:
        json.dump(project_data, f)

    print(f"Generated self-contained GeoLibre project files with inline payloads:\n  -> {proj_path_json}\n  -> {proj_path_geolibre}")

if __name__ == "__main__":
    main()
