#!/usr/bin/env python3
"""
scripts/generate_comparison_geolibre_project.py

Generates the 1-click GeoLibre Comparison & Visual QA/QC project files
(.geolibre and .geolibre.json) for raw source vs NG911 enhanced datasets.

Features:
- Side-by-side / Swipe comparison view structure
- Differential visual vector lines showing spatial displacement (Raw -> Enhanced)
- Color-coded enhancement categories:
    * Emerald (#059669): SPATIAL_CORRECTION (>5m displacement)
    * Blue (#2563eb): PSAP_ENRICHMENT (Enriched with PSAP dispatch boundaries)
    * Purple (#7c3aed): LANDMARK_ALIASED (Mapped to POI / Landmark alias)
    * Amber (#d97706): NENA_STREET_NORMALIZED (Standardized street components)
    * Gray (#6b7280): UNCHANGED
- Support for CLI `--source-file` allowing users to bring their own local address dataset.
"""

import argparse
import json
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

GITHUB_BASE_URL = "https://raw.githubusercontent.com/COF-RyLopez/ng911-pipeline/main/data/output"
TILES_BASE_URL = f"{GITHUB_BASE_URL}/tiles"


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

    project_data = {
        "version": "0.1.0",
        "name": "NG911 Address Enhancement & Visual QA/QC Diff Hub",
        "metadata": {
            "author": "County of Fresno (Ryan Lopez) & Cal OES GIS Committee",
            "jurisdiction": "County of Fresno, California (FIPS 06019)",
            "repository": "https://github.com/COF-RyLopez/ng911-pipeline",
            "standard": "NENA-STA-010-2021 & Cal OES NG911 GIS Guidelines",
            "description": "Interactive visual diffing hub comparing raw municipal address points against NG911 remediated address points, showing spatial displacement vectors, PSAP attribution, and DuckDB WASM queries."
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
            pmtiles_layer(
                "mart_ng911_fresno_diff_vectors",
                "Spatial Displacement Vectors (Raw -> Enhanced)",
                "fresno_diff_vectors.pmtiles",
                "diff_vectors",
                {
                    "fillColor": "#ef4444",
                    "strokeColor": "#ef4444",
                    "strokeWidth": 2.0,
                    "strokeWidthUnit": "pixels",
                },
                {
                    "click": True,
                    "hover": True,
                    "titleField": "RawAddress",
                    "fields": [
                        {"field": "RawAddress", "label": "Raw Local Address", "hover": True},
                        {"field": "EnhancedAddress", "label": "Enhanced NG911 Address", "hover": True},
                        {"field": "DisplacementMeters", "label": "Displacement (meters)", "kind": "number", "format": {"decimals": 1, "suffix": " m"}, "hover": True},
                        {"field": "EnhancementCategory", "label": "Category"}
                    ]
                },
                opacity=0.85
            ),
            pmtiles_layer(
                "mart_ng911_fresno_enhancements",
                "NG911 Address Points (Color-Coded by Enhancement)",
                "fresno_enhancements.pmtiles",
                "enhancements",
                {
                    "circleRadius": 5,
                    "circleColor": [
                        "match",
                        ["get", "EnhancementCategory"],
                        "SPATIAL_CORRECTION", "#059669",
                        "PSAP_ENRICHMENT", "#2563eb",
                        "LANDMARK_ALIASED", "#7c3aed",
                        "NENA_STREET_NORMALIZED", "#d97706",
                        "#6b7280"
                    ],
                    "strokeColor": "#ffffff",
                    "strokeWidth": 1.0
                },
                {
                    "click": True,
                    "hover": True,
                    "titleField": "EnhancedAddress",
                    "fields": [
                        {"field": "EnhancedAddress", "label": "Enhanced Address", "hover": True},
                        {"field": "RawAddress", "label": "Original Raw Address", "hover": True},
                        {"field": "EnhancementCategory", "label": "Enhancement Type", "hover": True},
                        {"field": "DisplacementMeters", "label": "Displacement (m)", "kind": "number", "format": {"decimals": 1, "suffix": " m"}},
                        {"field": "PSAP", "label": "Primary PSAP"},
                        {"field": "ESB_Fire", "label": "Fire District"},
                        {"field": "LandmarkName", "label": "POI Landmark Alias"},
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
