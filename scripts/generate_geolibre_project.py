#!/usr/bin/env python3
"""
scripts/generate_geolibre_project.py

Generates a native GeoLibre Project file (.geolibre and .geolibre.json) for the Fresno County NG911 Pilot.
Includes:
- Pre-styled layers (Fishbones in high-visibility red, SSAP in blue, RCL in emerald)
- Detailed NENA attribute popup configurations
- Built-in DuckDB Dashboard charts (Fishbone offset histogram, conflation distribution)
- Default map extent centered on Fresno County metro
"""

import os
import json

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PROJECT_DATA = {
    "version": "0.1.0",
    "name": "Fresno County NG911 QA/QC & Conflation Pilot",
    "metadata": {
        "author": "Antigravity NG911 Pipeline",
        "jurisdiction": "County of Fresno, California (FIPS 06019)",
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
            "source": {
                "type": "geojson",
                "url": "http://localhost:8088/mart_ng911_fresno_fishbones_sample.geojson"
            },
            "sourcePath": "http://localhost:8088/mart_ng911_fresno_fishbones_sample.geojson",
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
            "source": {
                "type": "geojson",
                "url": "http://localhost:8088/mart_ng911_fresno_ssap_sample.geojson"
            },
            "sourcePath": "http://localhost:8088/mart_ng911_fresno_ssap_sample.geojson",
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
            "source": {
                "type": "geojson",
                "url": "http://localhost:8088/mart_ng911_fresno_rcl_sample.geojson"
            },
            "sourcePath": "http://localhost:8088/mart_ng911_fresno_rcl_sample.geojson",
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

def main():
    proj_path_json = os.path.join(OUTPUT_DIR, "fresno_ng911_pilot.geolibre.json")
    proj_path_geolibre = os.path.join(OUTPUT_DIR, "fresno_ng911_pilot.geolibre")

    with open(proj_path_json, "w") as f:
        json.dump(PROJECT_DATA, f, indent=2)

    with open(proj_path_geolibre, "w") as f:
        json.dump(PROJECT_DATA, f, indent=2)

    print(f"Generated GeoLibre project files:\n  -> {proj_path_json}\n  -> {proj_path_geolibre}")

if __name__ == "__main__":
    main()
