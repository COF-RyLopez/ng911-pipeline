#!/usr/bin/env python3
"""
scripts/generate_geolibre_project.py

Generates the GeoLibre Project file (.geolibre and .geolibre.json) for the
Fresno County NG911 Pilot.
Includes:
- Pre-styled layers:
  1. Emergency Service Boundaries (ESBs: CAD/PSAP, Fire Districts, City Limits)
  2. Authoritative Road Centerlines (RCL with synthesized ranges)
  3. Site/Structure Address Points (SSAP with PSAP, Fire, Muni & Landmark attribution)
  4. QA/QC Fishbone Vectors (snapping distances and offset flags)
- 100% of features for every layer:
  - ESB (80 polygons) is small enough to inline as GeoJSON.
  - RCL, SSAP and Fishbones are streamed as PMTiles vector tiles from GitHub
    (built by scripts/build_pmtiles.py). Inlining them as GeoJSON caps out at a
    sample of ~40k features before the project exceeds GitHub's file limits,
    which is why earlier versions of the map looked incomplete.
- Detailed NENA attribute popup configurations
- Default map extent centered on Fresno County metro

The PMTiles layer shape mirrors `geolibre.project.pmtiles_layer()` from the
upstream GeoLibre Python package (opengeos/GeoLibre).
"""

import os
import json

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
    """A GeoLibre `pmtiles` vector layer streamed by HTTP range requests."""
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
            # Must be non-empty or GeoLibre never adds the source (see upstream pmtiles_layer()).
            "nativeLayerIds": [layer_id],
        },
        "popup": popup,
    }


def main():
    esb_geojson = load_geojson("mart_ng911_fresno_esb_sample.geojson")

    for f in ("fresno_rcl.pmtiles", "fresno_ssap.pmtiles", "fresno_fishbones.pmtiles"):
        if not os.path.exists(os.path.join(OUTPUT_DIR, "tiles", f)):
            print(f"WARNING: data/output/tiles/{f} missing. Run scripts/build_pmtiles.py first.")

    project_data = {
        "version": "0.1.0",
        "name": "Fresno County NG911 Statewide Dispatch & QA/QC Hub",
        "metadata": {
            "author": "County of Fresno (Ryan Lopez)",
            "jurisdiction": "County of Fresno, California (FIPS 06019)",
            "repository": "https://github.com/COF-RyLopez/ng911-pipeline",
            "standard": "NENA-STA-010-2021 & Cal OES NG911 GIS Guidelines",
            "description": "Statewide cloud-native NG911 emergency dispatch layers: SSAP address points, Road Centerlines, Emergency Service Boundaries, and automated QA/QC validation. 100% of Fresno County features, streamed as PMTiles."
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
                "id": "mart_ng911_fresno_esb",
                "name": "Emergency Service Boundaries (PSAP, Fire, Muni)",
                "type": "geojson",
                "visible": True,
                "opacity": 0.45,
                "geojson": esb_geojson,
                "source": {
                    "type": "geojson",
                    "url": f"{GITHUB_BASE_URL}/mart_ng911_fresno_esb_sample.geojson"
                },
                "sourcePath": f"{GITHUB_BASE_URL}/mart_ng911_fresno_esb_sample.geojson",
                "style": {
                    "fillColor": "#d97706",
                    "fillOpacity": 0.25,
                    "strokeColor": "#b45309",
                    "strokeWidth": 2.0,
                    "strokeWidthUnit": "pixels",
                    "minZoom": 0,
                    "maxZoom": 24
                },
                "popup": {
                    "click": True,
                    "hover": True,
                    "titleField": "Agency_Name",
                    "fields": [
                        {"field": "Agency_Name", "label": "Agency / District", "hover": True},
                        {"field": "Agency_Type", "label": "Boundary Type (PSAP/FIRE/MUNI)", "hover": True},
                        {"field": "Agency_Code", "label": "Agency Code"},
                        {"field": "ServiceNum", "label": "Dispatch Phone"},
                        {"field": "Area_Code", "label": "CAD Area Code"},
                        {"field": "ESB_NGUID", "label": "NENA ESB NGUID"}
                    ]
                }
            },
            pmtiles_layer(
                "mart_ng911_fresno_rcl",
                "NENA Road Centerlines (All 53,474)",
                "fresno_rcl.pmtiles",
                "rcl",
                {
                    "fillColor": "#059669",
                    "strokeColor": "#059669",
                    "strokeWidth": 2.0,
                    "strokeWidthUnit": "pixels",
                },
                {
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
                },
            ),
            pmtiles_layer(
                "mart_ng911_fresno_fishbones",
                "QA/QC Fishbone Vectors (All 365,316)",
                "fresno_fishbones.pmtiles",
                "fishbones",
                {
                    "fillColor": "#ef4444",
                    "strokeColor": "#ef4444",
                    "strokeWidth": 1.5,
                    "strokeWidthUnit": "pixels",
                },
                {
                    "click": True,
                    "hover": True,
                    "titleField": "STN",
                    "fields": [
                        {"field": "HNO", "label": "House Number", "hover": True},
                        {"field": "STN", "label": "Street Name", "hover": True},
                        {"field": "DistanceMeters", "label": "Distance to Centerline (m)", "kind": "number", "format": {"decimals": 1, "suffix": " m"}, "hover": True},
                        {"field": "IsExcessiveOffset", "label": "Excessive Offset (>50m)"},
                        {"field": "IsRangeViolation", "label": "Range Violation"},
                        {"field": "FishboneID", "label": "NENA Fishbone URN"},
                        {"field": "SSAP_NGUID", "label": "Matched SSAP Point"},
                        {"field": "RCL_NGUID", "label": "Matched Road Segment"}
                    ]
                },
            ),
            # Address points last so they draw on top of the fishbones that end on them.
            pmtiles_layer(
                "mart_ng911_fresno_ssap",
                "NENA SSAP Address Points (All 466,751)",
                "fresno_ssap.pmtiles",
                "ssap",
                {
                    "circleRadius": 4,
                    "fillColor": "#2563eb",
                    "fillOpacity": 0.9,
                    "strokeColor": "#ffffff",
                    "strokeWidth": 1.0,
                },
                {
                    "click": True,
                    "hover": True,
                    "titleField": "HNO",
                    "fields": [
                        {"field": "HNO", "label": "House Number", "hover": True},
                        {"field": "STN", "label": "Street Name", "hover": True},
                        {"field": "Unit", "label": "Unit"},
                        {"field": "PSAP", "label": "CAD / PSAP Routing", "hover": True},
                        {"field": "ESB_Fire", "label": "Fire District", "hover": True},
                        {"field": "LandmarkName", "label": "Landmark / POI Alias", "hover": True},
                        {"field": "Muni", "label": "Jurisdiction / Muni"},
                        {"field": "CommunityName", "label": "Postal Community"},
                        {"field": "ConflationStatus", "label": "Conflation Status"},
                        {"field": "SSAP_NGUID", "label": "NENA SSAP NGUID"}
                    ]
                },
            ),
        ],
        "interaction": {
            "identify": ["mart_ng911_fresno_ssap", "mart_ng911_fresno_fishbones", "mart_ng911_fresno_rcl", "mart_ng911_fresno_esb"],
            "controls": {
                "search": True,
                "measure": True,
                "navigation": True,
                "scale": True
            }
        }
    }

    # Validate project schema with Pydantic v2 before writing to disk
    try:
        from ng911_schemas import GeoLibreProjectConfig
        validated_proj = GeoLibreProjectConfig.model_validate(project_data)
        validated_dict = validated_proj.model_dump(mode="json", exclude_none=True)
    except Exception as e:
        print(f"Warning: GeoLibre Pydantic validation notice: {e}")
        validated_dict = project_data

    proj_path_json = os.path.join(OUTPUT_DIR, "fresno_ng911_pilot.geolibre.json")
    proj_path_geolibre = os.path.join(OUTPUT_DIR, "fresno_ng911_pilot.geolibre")

    for path in (proj_path_json, proj_path_geolibre):
        with open(path, "w") as f:
            json.dump(validated_dict, f, indent=2)

    size_mb = os.path.getsize(proj_path_json) / 1e6
    print(f"Generated GeoLibre project ({size_mb:.1f} MB, PMTiles-streamed layers):\n  -> {proj_path_json}\n  -> {proj_path_geolibre}")


if __name__ == "__main__":
    main()
