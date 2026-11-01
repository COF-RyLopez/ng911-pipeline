#!/usr/bin/env python3
"""Print an ArcGIS layer's fields and sample attribute rows: python scripts/inspect_esri_layer.py URL [where] [n]"""
import json
import sys
import urllib.parse

sys.path.insert(0, __import__("os").path.dirname(__file__))
from discover_county_endpoints import get_json  # noqa: E402

url, where, n = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "1=1"), int(sys.argv[3]) if len(sys.argv) > 3 else 12
meta = get_json(url)
print("FIELDS:", [(f["name"], f["type"].replace("esriFieldType", "")) for f in meta.get("fields", [])])
q = urllib.parse.urlencode({"where": where, "outFields": "*", "returnGeometry": "false", "resultRecordCount": n})
for f in get_json(f"{url}/query?{q}").get("features", []):
    print("ROW:", json.dumps({k: v for k, v in f["attributes"].items() if v not in (None, "", " ")}))
