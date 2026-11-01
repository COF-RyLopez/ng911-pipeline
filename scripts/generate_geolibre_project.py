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
  - RCL, SSAP and Fishbones are streamed as PMTiles vector tiles from Cloudflare R2
    (built by scripts/build_pmtiles.py). Inlining them as GeoJSON caps out at a
    sample of ~40k features before the project gets too large,
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

# Outputs are built by CI and published to Cloudflare R2 (scripts/publish_to_r2.py), not committed.
GITHUB_BASE_URL = os.environ.get("R2_PUBLIC_URL", "https://pub-152dce9299c94555bb415d992fe120e7.r2.dev").rstrip("/")
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


def geojson_layer(layer_id, name, filename, geojson, style, popup, opacity=1.0):
    """A GeoLibre `geojson` layer: features inline, plus the published URL they came from."""
    url = f"{GITHUB_BASE_URL}/{filename}"
    return {
        "id": layer_id, "name": name, "type": "geojson", "visible": True, "opacity": opacity,
        "geojson": geojson, "source": {"type": "geojson", "url": url}, "sourcePath": url,
        "style": {"strokeWidthUnit": "pixels", "minZoom": 0, "maxZoom": 24, **style},
        "popup": popup,
    }


# Product 2 boundary review: one layer per disagreement cause (GeoLibre styles are one colour per layer).
CAUSES = [
    ("FILED_CHANGE", "Filed annexation / correction (timing)", "#3b82f6"),
    ("SLIVER", "Sliver (same line drawn twice)", "#94a3b8"),
    ("ROAD_RIGHT_OF_WAY", "Road right-of-way (which city owns the road)", "#eab308"),
    ("UNEXPLAINED", "Unexplained (for county / LAFCo)", "#ef4444"),
]


def boundary_layers():
    """Reconciled city boundaries, city disagreements by cause, and county-line disagreements.
    Writes one GeoJSON per cause beside the full file so each layer's URL matches its inline features."""
    layers = []
    city = load_geojson("boundary_comparison/city_boundary_discrepancies.geojson")
    city_popup = {"click": True, "hover": True, "titleField": "City", "fields": [
        {"field": "City", "label": "City", "hover": True},
        {"field": "Side", "label": "Only in (ONLY_IN_STATE = CDTFA, ONLY_IN_LOCAL = county)", "hover": True},
        {"field": "Cause", "label": "Likely cause", "hover": True},
        {"field": "AreaKm2", "label": "Area (km²)"},
        {"field": "MeanWidthM", "label": "Mean width (m)"},
        {"field": "PctLengthAlongRoad", "label": "% of length along a county road"},
        {"field": "FiledChangeLayer", "label": "Filed change layer"},
    ]}
    for cause, label, color in CAUSES:
        fc = {"type": "FeatureCollection",
              "features": [f for f in city["features"] if f["properties"].get("Cause") == cause]}
        fname = f"boundary_comparison/city_boundary_discrepancies_{cause.lower()}.geojson"
        with open(os.path.join(OUTPUT_DIR, fname), "w") as f:
            json.dump(fc, f)
        layers.append(geojson_layer(
            f"city_boundary_{cause.lower()}", f"City limits vs CDTFA: {label}", fname, fc,
            {"fillColor": color, "fillOpacity": 0.45, "strokeColor": color, "strokeWidth": 1.0},
            city_popup))
    layers.append(geojson_layer(
        "county_boundary_discrepancies", "County line vs CDTFA (Overture / TIGER differences)",
        "boundary_comparison/county_boundary_discrepancies.geojson",
        load_geojson("boundary_comparison/county_boundary_discrepancies.geojson"),
        {"fillColor": "#f97316", "fillOpacity": 0.35, "strokeColor": "#c2410c", "strokeWidth": 1.0},
        {"click": True, "hover": True, "titleField": "ComparedTo", "fields": [
            {"field": "ComparedTo", "label": "Compared with CDTFA", "hover": True},
            {"field": "Side", "label": "Only in (ONLY_IN_STATE = CDTFA)", "hover": True},
            {"field": "Cause", "label": "Likely cause"},
            {"field": "AreaKm2", "label": "Area (km²)"},
            {"field": "CountyAddressPoints", "label": "County address points inside", "hover": True},
        ]}))
    # Reconciled lines on top of the disagreement fills
    layers.append(geojson_layer(
        "reconciled_city_boundaries", "Reconciled city boundaries (advisory)",
        "boundary_comparison/reconciled_city_boundaries.geojson",
        load_geojson("boundary_comparison/reconciled_city_boundaries.geojson"),
        {"fillColor": "#a78bfa", "fillOpacity": 0.0, "strokeColor": "#7c3aed", "strokeWidth": 2.5},
        {"click": True, "hover": True, "titleField": "City", "fields": [
            {"field": "City", "label": "City", "hover": True},
            {"field": "AreaKm2", "label": "Area (km²)", "hover": True},
            {"field": "ChangeFromCdtfaKm2", "label": "Change from CDTFA (km²)"},
            {"field": "PiecesTakenFromCounty", "label": "Pieces taken from the county line"},
            {"field": "UnexplainedPiecesKept", "label": "Unexplained pieces (CDTFA line kept)"},
            {"field": "Status", "label": "Status"},
        ]}))
    return layers


OSM_ISSUES = [
    ("MISSING_IN_OSM", "Missing in OpenStreetMap", "#f97316"),
    ("NAME_DIFFERS", "Different name in OpenStreetMap", "#eab308"),
]


def osm_fix_layers():
    """County roads OpenStreetMap (Overture's road source) is missing or names differently, one layer per
    issue, each with its own published GeoJSON so the inline features and the URL match."""
    fixes = load_geojson("open_data_fixes/osm_road_fixes.geojson")
    popup = {"click": True, "hover": True, "titleField": "CountyStreetName", "fields": [
        {"field": "CountyStreetName", "label": "County street name", "hover": True},
        {"field": "Issue", "label": "Issue", "hover": True},
        {"field": "OsmName", "label": "Name in OpenStreetMap"},
        {"field": "LengthM", "label": "Length (m)"},
        {"field": "OsmEditUrl", "label": "Fix in OpenStreetMap"},
    ]}
    layers = []
    for issue, label, color in OSM_ISSUES:
        fc = {"type": "FeatureCollection",
              "features": [f for f in fixes["features"] if f["properties"].get("Issue") == issue]}
        fname = f"open_data_fixes/osm_road_fixes_{issue.lower()}.geojson"
        os.makedirs(os.path.dirname(os.path.join(OUTPUT_DIR, fname)), exist_ok=True)
        with open(os.path.join(OUTPUT_DIR, fname), "w") as f:
            json.dump(fc, f)
        layers.append(geojson_layer(
            f"osm_road_fixes_{issue.lower()}", f"OpenStreetMap road fixes: {label}", fname, fc,
            {"fillColor": color, "fillOpacity": 0.0, "strokeColor": color, "strokeWidth": 3.0}, popup))
    return layers


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
            *boundary_layers(),
            *osm_fix_layers(),
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
                        {"field": "PSAP", "label": "Law dispatch area (PSAP stand-in)", "hover": True},
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
            "identify": ["mart_ng911_fresno_ssap", "mart_ng911_fresno_fishbones", "mart_ng911_fresno_rcl", "mart_ng911_fresno_esb",
                         "reconciled_city_boundaries", "county_boundary_discrepancies",
                         *[f"osm_road_fixes_{i.lower()}" for i, _, _ in OSM_ISSUES],
                         *[f"city_boundary_{c.lower()}" for c, _, _ in CAUSES]],
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
    with open(proj_path_json, "w") as f:
        json.dump(validated_dict, f, separators=(",", ":"))  # compact: inline boundary GeoJSON is a few MB

    size_mb = os.path.getsize(proj_path_json) / 1e6
    print(f"Generated GeoLibre project ({size_mb:.1f} MB, PMTiles-streamed layers):\n  -> {proj_path_json}")


if __name__ == "__main__":
    main()
