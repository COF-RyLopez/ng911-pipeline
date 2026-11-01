#!/usr/bin/env python3
"""
scripts/oa_conform_audit.py

Overture's US addresses are OpenAddresses records, and OpenAddresses reads each county's layer through a
source definition (sources/us/<st>/*.json) whose "conform" maps county fields to number / street / unit.
This audit checks those mappings against the live county ArcGIS layers, to find fixes worth a PR to
openaddresses/openaddresses (which then flow into Overture):

  MISSING_FIELD   a mapped field no longer exists on the layer (renamed upstream: the source is broken)
  MOSTLY_EMPTY    a mapped number/street field is filled on under half the layer's features
  BETTER_FIELD    an unmapped address-like field on the layer is filled more often than a mostly-empty mapped one

Usage (after cloning OpenAddresses as in discover_endpoints.yml):
  python scripts/oa_conform_audit.py oa/sources/us/ca
Writes data/output/discovery/<state>_oa_conform_audit.csv.
"""
import csv
import glob
import json
import os
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from discover_county_endpoints import OUT_DIR, get_json  # noqa: E402

ROLES = ("number", "street", "unit")
CANDIDATE = re.compile(r"addr|situs|house|hse|st_?num|street|st_?name|stname|full_?add|site_?add|num", re.I)
MOSTLY_EMPTY = 0.5  # ponytail: under half filled flags a field; rural parcel layers legitimately sit near this


def conform_fields(value):
    """Field names a conform entry reads: "F", ["F1", "F2"], or {"function": ..., "field(s)": ...} (nested)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [f for v in value for f in conform_fields(v)]
    if isinstance(value, dict):
        out = conform_fields(value.get("field", [])) + conform_fields(value.get("fields", []))
        for step in value.get("functions", []):  # "chain"
            out += conform_fields(step)
        return out
    return []


def count(url, where):
    q = urllib.parse.urlencode({"where": where, "returnCountOnly": "true"})
    return get_json(f"{url}/query?{q}").get("count")


def filled(url, field, ftype):
    if ftype in ("esriFieldTypeString",):
        where = f"{field} IS NOT NULL AND {field} <> '' AND {field} <> ' '"
    elif ftype in ("esriFieldTypeInteger", "esriFieldTypeSmallInteger", "esriFieldTypeDouble", "esriFieldTypeSingle"):
        where = f"{field} IS NOT NULL AND {field} <> 0"
    else:
        where = f"{field} IS NOT NULL"
    return count(url, where)


def audit(source_file, layer):
    url = layer.get("data", "").split("?")[0].rstrip("/")
    row = {"source_file": source_file, "layer": layer.get("name", ""), "url": url}
    try:
        meta = get_json(url)
        types = {f["name"].upper(): (f["name"], f["type"]) for f in meta.get("fields", [])}
        total = count(url, "1=1")
    except Exception as e:
        return [{**row, "issue": "UNREACHABLE", "detail": f"{type(e).__name__}: {str(e)[:120]}"}]
    if not total:
        return [{**row, "issue": "EMPTY_LAYER", "detail": "layer has no features"}]

    # a role is judged by its best-filled field: street lists optional parts (pre/post direction) that are
    # rightly empty most of the time, so only a role whose every field is mostly empty is flagged
    conform, issues, mapped, weak = layer.get("conform") or {}, [], set(), {}
    for role in ROLES:
        best, best_field = None, None
        for f in conform_fields(conform.get(role)):
            if f.startswith("oa:"):
                continue  # an intermediate value an earlier conform function made, not a county field
            mapped.add(f.upper())
            if f.upper() not in types:
                issues.append({**row, "issue": "MISSING_FIELD", "role": role, "field": f,
                               "detail": f"'{f}' is not on the layer"})
                continue
            name, ftype = types[f.upper()]
            n = filled(url, name, ftype)
            if n is not None and (best is None or n > best):
                best, best_field = n, name
        if role != "unit" and best is not None and best / total < MOSTLY_EMPTY:
            weak[role] = best
            issues.append({**row, "issue": "MOSTLY_EMPTY", "role": role, "field": best_field,
                           "pct_filled": round(100 * best / total, 1), "detail": f"{best:,} of {total:,} features"})
    if weak:
        worst = min(weak.values())
        for key, (name, ftype) in types.items():
            if key in mapped or not CANDIDATE.search(name) or ftype in ("esriFieldTypeOID", "esriFieldTypeGeometry"):
                continue
            n = filled(url, name, ftype)
            if n and n > worst and n / total >= MOSTLY_EMPTY:
                issues.append({**row, "issue": "BETTER_FIELD", "role": "/".join(weak), "field": name,
                               "pct_filled": round(100 * n / total, 1),
                               "detail": f"unmapped, filled on {n:,} of {total:,} (mapped best {worst:,})"})
    return [{**i, "total_features": total} for i in issues] or [{**row, "issue": "OK", "total_features": total}]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src_dir = sys.argv[1]
    state = os.path.basename(os.path.normpath(src_dir))
    jobs = []
    for path in sorted(glob.glob(os.path.join(src_dir, "*.json"))):
        for layer in json.load(open(path)).get("layers", {}).get("addresses", []):
            if layer.get("protocol") == "ESRI":
                jobs.append((os.path.basename(path), layer))
    print(f"Auditing {len(jobs)} ESRI address sources in {src_dir}...")
    with ThreadPoolExecutor(8) as pool:
        rows = [r for rs in pool.map(lambda j: audit(*j), jobs) for r in rs]

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{state}_oa_conform_audit.csv")
    cols = ["source_file", "layer", "issue", "role", "field", "pct_filled", "total_features", "detail", "url"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["issue"] == "OK", r["issue"], r["source_file"])))
    by = {}
    for r in rows:
        by[r["issue"]] = by.get(r["issue"], 0) + 1
    print("  " + ", ".join(f"{k}: {v}" for k, v in sorted(by.items())))
    for r in rows:
        if r["issue"] in ("MISSING_FIELD", "MOSTLY_EMPTY", "BETTER_FIELD"):
            print(f"    {r['issue']:<13} {r['source_file']:<28} {r.get('field', ''):<20} {r.get('detail', '')}")
    print(f"Wrote {out}")


def _selfcheck():
    assert conform_fields("HOUSE_NUM") == ["HOUSE_NUM"]
    assert conform_fields(["PREFIX_DIR", "ST_NAME"]) == ["PREFIX_DIR", "ST_NAME"]
    assert conform_fields({"function": "prefixed_number", "field": "Situs"}) == ["Situs"]
    assert conform_fields({"function": "join", "fields": ["A", "B"]}) == ["A", "B"]
    assert conform_fields({"function": "chain", "functions": [{"function": "regexp", "field": "X"}]}) == ["X"]


if __name__ == "__main__":
    _selfcheck()
    main()
