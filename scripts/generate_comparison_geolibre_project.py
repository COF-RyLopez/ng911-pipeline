#!/usr/bin/env python3
"""
scripts/generate_comparison_geolibre_project.py

Generates 1-click GeoLibre Comparison, QA/QC & Actionable Remediation project files
(.geolibre and .geolibre.json) for raw source vs NG911 enhanced datasets.

Features:
- Focused street-level default view (zoom 16.5) so building footprints and points are immediately visible.
- Overture Building Footprints polygon layer (visual containment check)
- Color-coded rule-violation symbology:
    * Red (#dc2626): CRITICAL_POS_OFFSET / Missing mandatory NENA fields
    * Orange (#ea580c): OUTSIDE_BUILDING_FOOTPRINT (Positioning audit required)
    * Yellow (#eab308): MISSING_NENA_MANDATORY_FIELD
    * Green (#16a34a): VALIDATED_OK (Inside building footprint & valid street)
- QA/QC Fishbone snapping vectors connecting points to road centerlines
- Authoritative NENA Road Centerlines
- Clickable Mapillary street view links for ground-truth driveway/access validation
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


def load_sample_geojson(filename, limit=1500):
    path = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                return {
                    "type": "FeatureCollection",
                    "features": data.get("features", [])[:limit]
                }
        except Exception:
            pass
    return {"type": "FeatureCollection", "features": []}


R2_BASE_URL = os.environ.get("R2_PUBLIC_URL", "https://pub-152dce9299c94555bb415d992fe120e7.r2.dev")


def build_project(base_url, is_local=False, is_r2=False):
    raw_base = R2_BASE_URL if is_r2 else (GITHUB_PAGES_BASE_URL if not is_local else LOCAL_BASE_URL)

    # Note: GeoLibre Web app (browser build) does not bundle the PMTiles decoder,
    # so PMTiles only applies to local desktop/Tauri environments.
    # For R2 web viewing, we use GeoJSON with R2 source URLs and pre-cached features.
    use_pmtiles = is_local

    bldg_geojson = load_sample_geojson("overture_buildings_sample.geojson", limit=1500) if not use_pmtiles else None
    rcl_geojson = load_sample_geojson("mart_ng911_fresno_rcl_sample.geojson", limit=1500) if not use_pmtiles else None
    fishbones_geojson = load_sample_geojson("mart_ng911_fresno_fishbones_sample.geojson", limit=1500) if not use_pmtiles else None
    remediation_geojson = load_sample_geojson("remediation/county_remediation_points_sample.geojson", limit=1500) if not use_pmtiles else None

    proj_label = "(Cloudflare R2)" if is_r2 else ("(Local Server)" if is_local else "(Cloud Remote)")

    return {
        "version": "0.1.0",
        "name": f"NG911 Address Remediation & Building Footprint Hub {proj_label}",
        "metadata": {
            "author": "County of Fresno (Ryan Lopez) & Cal OES GIS Committee",
            "jurisdiction": "County of Fresno, California (FIPS 06019)",
            "repository": "https://github.com/COF-RyLopez/ng911-pipeline",
            "standard": "NENA-STA-010-2021 & Cal OES NG911 GIS Guidelines",
            "description": "Interactive visual QA/QC and remediation hub for county GIS departments. Displays address point containment inside Overture building footprints, QA/QC fishbone snapping vectors, road centerlines, and Mapillary ground-truth street view.",
            "plugins": ["swipe", "geo-editor", "dimensions", "mapillary"]
        },
        "mapView": {
            "center": [-119.8710, 36.6757],
            "zoom": 14.5,
            "bearing": 0,
            "pitch": 0,
            "bbox": [-119.9500, 36.6001, -119.7921, 36.7514]
        },
        "basemapStyleUrl": "https://tiles.openfreemap.org/styles/positron",
        "basemapVisible": True,
        "basemapOpacity": 1.0,
        "primaryRenderer": "maplibre",
        "layers": [
            {
                "id": "overture_buildings_layer",
                "name": "🏢 Overture Building Footprints (Containment Check)",
                "type": "pmtiles" if use_pmtiles else "geojson",
                "visible": True,
                "opacity": 0.45,
                "bounds": [-119.95, 36.60, -119.75, 36.75],
                "bbox": [-119.95, 36.60, -119.75, 36.75],
                "geojson": bldg_geojson,
                "source": {
                    "type": "vector" if use_pmtiles else "geojson",
                    "url": f"{raw_base}/tiles/fresno_buildings.pmtiles" if use_pmtiles else f"{raw_base}/overture_buildings_sample.geojson",
                    "data": f"{raw_base}/overture_buildings_sample.geojson" if not use_pmtiles else None,
                    "sourceId": "overture_buildings_layer",
                    "sourceLayers": ["buildings"] if use_pmtiles else None,
                    "tileType": "vector" if use_pmtiles else None
                },
                "sourcePath": f"{raw_base}/tiles/fresno_buildings.pmtiles" if use_pmtiles else f"{raw_base}/overture_buildings_sample.geojson",
                "style": {
                    "fillColor": "#475569",
                    "fillOpacity": 0.45,
                    "strokeColor": "#1e293b",
                    "strokeWidth": 1.5,
                    "strokeWidthUnit": "pixels",
                    "minZoom": 0,
                    "maxZoom": 24
                },
                "popup": {
                    "click": True,
                    "hover": True,
                    "titleField": "building_id",
                    "fields": [
                        {"field": "building_id", "label": "Overture Building ID", "hover": True},
                        {"field": "building_class", "label": "Building Structure Class"},
                        {"field": "num_floors", "label": "Number of Floors"},
                        {"field": "height", "label": "Building Height (m)"}
                    ]
                }
            },
            {
                "id": "mart_ng911_fresno_rcl_layer",
                "name": "🛣️ Authoritative NENA Road Centerlines",
                "type": "pmtiles" if use_pmtiles else "geojson",
                "visible": True,
                "opacity": 0.85,
                "bounds": [-119.95, 36.60, -118.90, 37.25],
                "bbox": [-119.95, 36.60, -118.90, 37.25],
                "geojson": rcl_geojson,
                "source": {
                    "type": "vector" if use_pmtiles else "geojson",
                    "url": f"{raw_base}/tiles/fresno_rcl.pmtiles" if use_pmtiles else f"{raw_base}/mart_ng911_fresno_rcl_sample.geojson",
                    "data": f"{raw_base}/mart_ng911_fresno_rcl_sample.geojson" if not use_pmtiles else None,
                    "sourceId": "mart_ng911_fresno_rcl_layer",
                    "sourceLayers": ["rcl"] if use_pmtiles else None,
                    "tileType": "vector" if use_pmtiles else None
                },
                "sourcePath": f"{raw_base}/tiles/fresno_rcl.pmtiles" if use_pmtiles else f"{raw_base}/mart_ng911_fresno_rcl_sample.geojson",
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
                        {"field": "FromAddr_L", "label": "From Left (HNS)"},
                        {"field": "ToAddr_L", "label": "To Left (HNS)"},
                        {"field": "FromAddr_R", "label": "From Right (HNS)"},
                        {"field": "ToAddr_R", "label": "To Right (HNS)"},
                        {"field": "RoadClass", "label": "Road Functional Class"},
                        {"field": "RCL_NGUID", "label": "NENA RCL NGUID"}
                    ]
                }
            },
            {
                "id": "mart_ng911_fresno_fishbones_layer",
                "name": "📏 QA/QC Displacement Vectors & Fishbones (Address to Street)",
                "type": "pmtiles" if use_pmtiles else "geojson",
                "visible": True,
                "opacity": 0.9,
                "bounds": [-119.95, 36.60, -118.90, 37.25],
                "bbox": [-119.95, 36.60, -118.90, 37.25],
                "geojson": fishbones_geojson,
                "source": {
                    "type": "vector" if use_pmtiles else "geojson",
                    "url": f"{raw_base}/tiles/fresno_fishbones.pmtiles" if use_pmtiles else f"{raw_base}/mart_ng911_fresno_fishbones_sample.geojson",
                    "data": f"{raw_base}/mart_ng911_fresno_fishbones_sample.geojson" if not use_pmtiles else None,
                    "sourceId": "mart_ng911_fresno_fishbones_layer",
                    "sourceLayers": ["fishbones"] if use_pmtiles else None,
                    "tileType": "vector" if use_pmtiles else None
                },
                "sourcePath": f"{raw_base}/tiles/fresno_fishbones.pmtiles" if use_pmtiles else f"{raw_base}/mart_ng911_fresno_fishbones_sample.geojson",
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
                        {"field": "DistanceMeters", "label": "Displacement Offset (m)", "kind": "number", "format": {"decimals": 1, "suffix": " m"}, "hover": True},
                        {"field": "IsExcessiveOffset", "label": "Excessive Offset (>50m)"},
                        {"field": "IsRangeViolation", "label": "Range Violation"},
                        {"field": "FishboneID", "label": "NENA Fishbone URN"}
                    ]
                }
            },
            {
                "id": "mart_ng911_county_remediation_layer",
                "name": "📍 NG911 Address Remediation & Building Footprint Status",
                "type": "pmtiles" if use_pmtiles else "geojson",
                "visible": True,
                "opacity": 1.0,
                "bounds": [-119.95, 36.60, -118.90, 37.25],
                "bbox": [-119.95, 36.60, -118.90, 37.25],
                "geojson": remediation_geojson,
                "source": {
                    "type": "vector" if use_pmtiles else "geojson",
                    "url": f"{raw_base}/tiles/fresno_remediation.pmtiles" if use_pmtiles else f"{raw_base}/remediation/county_remediation_points_sample.geojson",
                    "data": f"{raw_base}/remediation/county_remediation_points_sample.geojson" if not use_pmtiles else None,
                    "sourceId": "mart_ng911_county_remediation_layer",
                    "sourceLayers": ["remediation"] if use_pmtiles else None,
                    "tileType": "vector" if use_pmtiles else None
                },
                "sourcePath": f"{raw_base}/tiles/fresno_remediation.pmtiles" if use_pmtiles else f"{raw_base}/remediation/county_remediation_points_sample.geojson",
                "style": {
                    "circleRadius": 6,
                    "fillColor": "#ea580c",
                    "fillOpacity": 0.9,
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
                        {"field": "SymbologyCategory", "label": "Rule Violation Category", "hover": True},
                        {"field": "BuildingFootprintStatus", "label": "Building Footprint Containment", "hover": True},
                        {"field": "SpatialOffsetMeters", "label": "Spatial Offset (m)", "kind": "number", "format": {"decimals": 1, "suffix": " m"}},
                        {"field": "RecommendedRemediationAction", "label": "Action Needed for Jurisdiction"},
                        {"field": "MapillaryGroundTruthURL", "label": "Mapillary Ground-Truth Link", "kind": "url"},
                        {"field": "SSAP_NGUID", "label": "NENA SSAP NGUID"}
                    ]
                }
            }
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="Generate GeoLibre QA/QC Comparison Project.")
    parser.add_argument("--source-file", help="Path to local user source dataset (.geojson, .parquet, .csv)", default=None)
    args = parser.parse_args()

    # 1. Build Remote Project (GitHub Pages / Raw with embedded samples)
    remote_proj = build_project(GITHUB_PAGES_BASE_URL, is_local=False, is_r2=False)
    json_path = os.path.join(OUTPUT_DIR, "ng911_address_comparison.geolibre.json")
    geolibre_path = os.path.join(OUTPUT_DIR, "ng911_address_comparison.geolibre")

    with open(json_path, "w") as f:
        json.dump(remote_proj, f, indent=2)
    with open(geolibre_path, "w") as f:
        json.dump(remote_proj, f, indent=2)

    # 2. Build Cloudflare R2 Project (High-performance full PMTiles streaming)
    r2_proj = build_project(R2_BASE_URL, is_local=False, is_r2=True)
    r2_json_path = os.path.join(OUTPUT_DIR, "ng911_address_comparison_r2.geolibre.json")
    r2_geolibre_path = os.path.join(OUTPUT_DIR, "ng911_address_comparison_r2.geolibre")

    with open(r2_json_path, "w") as f:
        json.dump(r2_proj, f, indent=2)
    with open(r2_geolibre_path, "w") as f:
        json.dump(r2_proj, f, indent=2)

    # 3. Build Local Project (http://localhost:8088/ Byte Serving URL)
    local_proj = build_project(LOCAL_BASE_URL, is_local=True, is_r2=False)
    local_json_path = os.path.join(OUTPUT_DIR, "ng911_address_comparison_local.geolibre.json")
    local_geolibre_path = os.path.join(OUTPUT_DIR, "ng911_address_comparison_local.geolibre")

    with open(local_json_path, "w") as f:
        json.dump(local_proj, f, indent=2)
    with open(local_geolibre_path, "w") as f:
        json.dump(local_proj, f, indent=2)

    print("Generated GeoLibre QA/QC Projects:")
    print(f"  Remote (Embedded) -> {json_path}")
    print(f"  Cloudflare R2     -> {r2_json_path}")
    print(f"  Local Byte-Server -> {local_json_path}")


if __name__ == "__main__":
    main()
