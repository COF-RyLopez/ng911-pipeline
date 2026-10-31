#!/usr/bin/env python3
"""
scripts/discover_county_endpoints.py

Product 2, step 1: find each county's (and city's) GIS endpoints, starting from OpenAddresses.

1. Index: every OpenAddresses source for the state lists its addresses / parcels / buildings /
   centerlines endpoints, with license, as the OA community has already verified them.
2. Crawl: each ArcGIS REST server those endpoints live on is listed (services + layers), and
   layer names are matched to the NG911 layers OA doesn't carry: road centerlines (where OA has
   none) and boundaries (city limits, fire, law, EMS/ESZ, PSAP).

Usage:
  git clone --depth 1 --filter=blob:none --sparse https://github.com/openaddresses/openaddresses oa
  git -C oa sparse-checkout set sources/us/ca
  python scripts/discover_county_endpoints.py oa/sources/us/ca

Writes data/output/discovery/<state>_endpoints.{json,csv} and <state>_discovery_summary.csv.
Crawl candidates are name matches, not verified layers: review before use.
"""

import csv
import glob
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(PROJECT_DIR, "data", "output", "discovery")
TIMEOUT = 20
MAX_SERVICES_PER_ROOT = 400  # ponytail: big AGOL orgs list thousands; raise if a county's layers get cut off

# Layer-name patterns -> NG911 layer kind. First match wins, so specific kinds come before generic.
KINDS = [
    ("psap", r"\bpsap"),
    ("esz", r"\besz\b|\besn\b|emergency.?service.?(zone|number)"),
    ("ems", r"\bems\b|ambulance"),
    ("fire", r"\bfire\b|\bfpd\b|fire.?protection|fire.?district|fire.?response"),
    ("law", r"\blaw\b|police|sheriff|\bbeat|patrol"),
    ("city_limits", r"city.?limit|incorporated|municipal.?bound|\bcities\b|city.?bound"),
    ("county_boundary", r"county.?bound|county.?line|county.?limit"),
    ("centerlines", r"center.?line|\bcl\b|\brcl\b|street|road|\broads?\b|transportation|\bstr?\b"),
]
KIND_GEOMETRY = {"centerlines": "esriGeometryPolyline"}  # every other kind is a polygon layer


def get_json(url):
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(f"{url}{sep}f=json", headers={"User-Agent": "ng911-pipeline endpoint discovery"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        d = json.load(resp)
    if "error" in d:
        raise RuntimeError(d["error"].get("message", "error"))
    return d


def classify(name, geometry_type):
    n = name.lower().replace("_", " ")
    for kind, pattern in KINDS:
        if re.search(pattern, n):
            want = KIND_GEOMETRY.get(kind, "esriGeometryPolygon")
            return kind if geometry_type == want else None
    return None


def server_root(url):
    m = re.match(r"(https?://.+?/rest/services)", url, re.I)
    return m.group(1).replace("/ArcGIS/rest/", "/arcgis/rest/") if m else None


def index_oa(src_dir):
    rows = []
    for path in sorted(glob.glob(os.path.join(src_dir, "*.json"))):
        d = json.load(open(path))
        cov = d.get("coverage", {})
        geoid = str(cov.get("US Census", {}).get("geoid", ""))
        jurisdiction = cov.get("city") or cov.get("county") or os.path.basename(path)[:-5]
        for layer_type, layers in d.get("layers", {}).items():
            for layer in layers:
                lic = layer.get("license")
                rows.append({
                    "source_file": os.path.basename(path),
                    "jurisdiction": jurisdiction,
                    "jurisdiction_type": "city" if "city" in cov else "county",
                    "county_fips": geoid if len(geoid) == 5 else "",
                    "layer_kind": layer_type,
                    "origin": "openaddresses",
                    "layer_name": layer.get("name", ""),
                    "geometry_type": "",
                    "protocol": layer.get("protocol", ""),
                    "url": layer.get("data", ""),
                    "license": (lic.get("text") or lic.get("url", "")) if isinstance(lic, dict) else (lic or ""),
                })
    return rows


def crawl_root(root):
    """List a server's services and their layers; return (candidate rows, error)."""
    try:
        services, folders = [], [""]
        while folders:
            folder = folders.pop()
            cat = get_json(f"{root}/{folder}".rstrip("/"))
            folders += [f for f in cat.get("folders", []) if not folder]
            services += [s for s in cat.get("services", []) if s.get("type") in ("FeatureServer", "MapServer")]
        rows = []
        for svc in services[:MAX_SERVICES_PER_ROOT]:
            svc_url = svc.get("url") or f"{root}/{svc['name']}/{svc['type']}"
            try:
                layers = get_json(svc_url).get("layers", [])
            except Exception:
                continue
            for lyr in layers:
                kind = classify(f"{svc['name']} {lyr.get('name', '')}", lyr.get("geometryType"))
                if kind:
                    rows.append({"layer_kind": kind, "layer_name": f"{svc['name']} / {lyr.get('name')}",
                                 "geometry_type": lyr.get("geometryType"), "url": f"{svc_url}/{lyr['id']}"})
        return rows, ""
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src_dir = sys.argv[1]
    state = os.path.basename(os.path.normpath(src_dir))
    rows = index_oa(src_dir)
    print(f"Indexed {len(rows)} OpenAddresses layers from {src_dir}")

    # Which jurisdictions sit on which ArcGIS server (one server can serve a county and its cities).
    by_root = {}
    for r in rows:
        root = server_root(r["url"]) if r["protocol"] == "ESRI" else None
        if root:
            by_root.setdefault(root, {})[r["source_file"]] = r
    print(f"Crawling {len(by_root)} ArcGIS servers...")
    with ThreadPoolExecutor(8) as pool:
        results = dict(zip(by_root, pool.map(crawl_root, by_root)))

    errors = {}
    for root, (cands, err) in results.items():
        if err:
            errors[root] = err
        seen = {r["url"] for r in rows}
        for src in by_root[root].values():
            for c in cands:
                if c["url"] in seen:
                    continue  # already an OA layer for this jurisdiction
                rows.append({**{k: src[k] for k in ("source_file", "jurisdiction", "jurisdiction_type", "county_fips")},
                             **c, "origin": "arcgis_catalog", "protocol": "ESRI", "license": ""})
    ok = len(by_root) - len(errors)
    print(f"  {ok} servers listed, {len(errors)} unreachable")

    os.makedirs(OUT_DIR, exist_ok=True)
    fields = list(rows[0].keys())
    with open(os.path.join(OUT_DIR, f"{state}_endpoints.json"), "w") as f:
        json.dump({"servers_unreachable": errors, "endpoints": rows}, f, indent=1)
    with open(os.path.join(OUT_DIR, f"{state}_endpoints.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)

    # One line per jurisdiction: what OA has, what the crawl found, what's still missing.
    kinds = ["addresses", "parcels", "buildings", "centerlines", "city_limits", "county_boundary",
             "fire", "law", "ems", "esz", "psap"]
    summary = {}
    for r in rows:
        s = summary.setdefault(r["source_file"], {"source_file": r["source_file"], "jurisdiction": r["jurisdiction"],
                                                  "jurisdiction_type": r["jurisdiction_type"],
                                                  "county_fips": r["county_fips"], **{k: "" for k in kinds}})
        tag = "oa" if r["origin"] == "openaddresses" else "candidate"
        if s[r["layer_kind"]] != "oa":
            s[r["layer_kind"]] = tag
    with open(os.path.join(OUT_DIR, f"{state}_discovery_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["source_file", "jurisdiction", "jurisdiction_type", "county_fips"] + kinds)
        w.writeheader()
        w.writerows(sorted(summary.values(), key=lambda s: (s["jurisdiction_type"] != "county", s["jurisdiction"])))

    counties = [s for s in summary.values() if s["jurisdiction_type"] == "county"]
    for k in ("centerlines", "city_limits", "fire", "law", "psap"):
        oa = sum(s[k] == "oa" for s in counties)
        cand = sum(s[k] == "candidate" for s in counties)
        print(f"  {k:12s} counties: {oa} from OpenAddresses, {cand} more with catalog candidates, "
              f"{len(counties) - oa - cand} none found")
    print(f"Wrote {OUT_DIR}/{state}_endpoints.json, .csv and {state}_discovery_summary.csv")


def _selfcheck():
    assert classify("REGIONAL_STREETS_VW / Streets", "esriGeometryPolyline") == "centerlines"
    assert classify("REGIONAL_STREETS_VW / Streets", "esriGeometryPolygon") is None  # street polygons aren't RCL
    assert classify("ELECTIONS_FIRE_DISTRICTS_VW / Fire Districts", "esriGeometryPolygon") == "fire"
    assert classify("REGIONAL_CITY_LIMITS_VW / City Limits", "esriGeometryPolygon") == "city_limits"
    assert classify("City_County_CAD / Sheriff Beats", "esriGeometryPolygon") == "law"
    assert classify("Parcels / Parcels", "esriGeometryPolygon") is None
    assert server_root("https://services3.arcgis.com/x/ArcGIS/rest/services/A/FeatureServer/1") == \
        "https://services3.arcgis.com/x/arcgis/rest/services"


if __name__ == "__main__":
    _selfcheck()
    main()
