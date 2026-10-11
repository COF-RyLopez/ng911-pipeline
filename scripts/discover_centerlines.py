#!/usr/bin/env python3
"""
Find street-centerline layers on the ArcGIS servers OpenAddresses already
references, and propose OpenAddresses `centerlines` layer entries for them.

    python scripts/discover_centerlines.py --oa ../openaddresses us/ca/fresno us/ca/kings ...

Writes data/output/centerline_discovery.json: ranked candidates per source,
each with a proposed OA layer object (conform mapping guessed from field names).
A human picks the right candidate before it goes into an OA PR.

ponytail: stdlib only, field mapping is name heuristics; review every pick.
"""
import argparse, json, math, os, re, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

STREETY = re.compile(r"street|road|centerline|center_line|\brcl\b|transport|segment", re.I)
NOT_STREETS = re.compile(r"light|(?<!s)trees?\b|street_?tree|sweep|closure|broadband|label|sewer|storm|rail|trail|bike|"
                         r"inspection|damage|closed|closure|stream|river|sidewalk|pavement|condition|calming|"
                         r"locator|geocode|anno", re.I)
# Field classifiers: first regex hit wins (matched against lower-cased field names).
FULL = r"^(full_?(st|str|street|road|rd)?_?name|name_?full|st_?full_?name|fullname|fullrdname|label_?name|road_?name|street_?name|streetname)$"
# Ordered like a NENA CompleteStNam: PreMod PreDir PreTyp Name PosTyp PosDir PosMod.
PARTS = [r"^st_?pre_?mod$",
         r"^(pre_?dir|prefix|st_?pre_?dir|str_?dir|st_?dir|street_?dir|fedirp|dirpre|sdirpre|predirection)$",
         r"^st_?pre_?typ(e)?$",
         r"^(st_?name|str_?name|stname|street|name|fename|sfeanme|base_?name|rd_?name)$",
         r"^(st_?type|st_?pos_?typ(e)?|str_?type|sttype|street_?type|type|fetype|sfeatyp)$",
         r"^(post_?dir|st_?pos_?dir|st_?post_?dir|str_?post_?dir|suf_?dir|sufdir|fedirs|dirsuf|sdirsuf|suffix|stsuffix|postdirection)$",
         r"^st_?pos_?mod$"]
RANGES = {"addr_from_left": r"^(l_?f_?add(r)?|l_?from(_?add(r)?)?|from_?left|left_?from|lf_?add|fraddl|from_?addr?_?l|l_?add_?fr(om)?|ladd_?fr(om)?|lefromadd)$",
          "addr_to_left": r"^(l_?t_?add(r)?|l_?to(_?add(r)?)?|to_?left|left_?to|lt_?add|toaddl|to_?addr?_?l|l_?add_?to|ladd_?to|letoadd)$",
          "addr_from_right": r"^(r_?f_?add(r)?|r_?from(_?add(r)?)?|from_?right|right_?from|rf_?add|fraddr|from_?addr?_?r|r_?add_?fr(om)?|radd_?fr(om)?|rtfromadd)$",
          "addr_to_right": r"^(r_?t_?add(r)?|r_?to(_?add(r)?)?|to_?right|right_?to|rt_?add|toaddr|to_?addr?_?r|r_?add_?to|radd_?to|rttoadd)$",
          "zip_left": r"^(zip_?l(eft)?|l_?zip|post_?code_?l|lzip)$",
          "zip_right": r"^(zip_?r(ight)?|r_?zip|post_?code_?r|rzip)$"}
ID = r"^(seg(ment)?_?id|centerlineid|str_?id|road_?seg_?id|roadsegid|rcl_?nguid|nguid|centerline_?id|cl_?id|street_?id|rd_?seg_?id|unique_?id)$"


def get(url, **params):
    params["f"] = "json"
    sep = "&" if "?" in url else "?"
    for attempt in range(3):  # public ArcGIS servers time out and rate-limit; retry with backoff
        try:
            with urllib.request.urlopen(url + sep + urllib.parse.urlencode(params), timeout=30) as r:
                d = json.load(r)
            return None if "error" in d else d
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def rest_root(url):
    m = re.match(r"(.*?/rest/services)", url, re.I)
    return m.group(1) if m else None


def services(root):
    top = get(root) or {}
    out = list(top.get("services", []))
    for folder in top.get("folders", [])[:40]:
        out += (get(f"{root}/{folder}") or {}).get("services", [])
    return [s for s in out if s.get("type") in ("FeatureServer", "MapServer")]


def pick(fields, pattern):
    return next((f for f in fields if re.match(pattern, f.lower())), None)


def conform_for(fields):
    c = {"format": "geojson"}
    if (i := pick(fields, ID)):
        c["id"] = i
    nena = pick(fields, r"^st_?pre_?typ(e)?$") and pick(fields, r"^st_?name$")
    if not nena and (n := pick(fields, FULL)):
        c["name"] = n
    else:
        parts = [pick(fields, p) for p in PARTS]
        if parts[3]:
            c["name"] = {"function": "join", "fields": [p for p in parts if p], "separator": " "}
    for tag, names in RANGES.items():
        if (f := pick(fields, names)):
            c[tag] = f
    return c


def inspect_layer(url):
    meta = get(url)
    if not meta or meta.get("geometryType") != "esriGeometryPolyline":
        return None
    fields = [f["name"] for f in meta.get("fields", [])]
    count = (get(url + "/query", where="1=1", returnCountOnly="true") or {}).get("count")
    conform = conform_for(fields)
    has_ranges = sum(k.startswith("addr_") for k in conform)
    # NG911 needs the complete network, so size dominates: log10(count) * 3.
    score = (3 if "name" in conform else 0) + has_ranges + (1 if "id" in conform else 0) \
        + round(3 * math.log10(count), 1) if count else -5
    score += 2 if STREETY.search(meta.get("name", "")) else 0
    score -= 4 if re.search(r"major|maintained|arterial|highway|hwy|alley|moratorium|sqf|copy", meta.get("name", ""), re.I) else 0
    return {"url": url, "layer": meta.get("name"), "count": count, "score": score,
            "fields": fields, "conform": conform}


def discover(root):
    urls = []
    for s in services(root):
        if not STREETY.search(s["name"]) or NOT_STREETS.search(s["name"]):
            continue
        base = f"{root}/{s['name']}/{s['type']}"
        for lyr in (get(base) or {}).get("layers", []):
            if not NOT_STREETS.search(lyr.get("name", "")):
                urls.append(f"{base}/{lyr['id']}")
    # A service often publishes the same layer as MapServer and FeatureServer; keep one.
    seen, uniq = set(), []
    for u in sorted(urls, key=lambda u: "MapServer" in u):
        key = re.sub(r"/(Feature|Map)Server/", "/", u)
        if key not in seen:
            seen.add(key); uniq.append(u)
    urls = uniq
    with ThreadPoolExecutor(4) as ex:
        found = [r for r in ex.map(inspect_layer, urls) if r]
    return sorted(found, key=lambda r: (-r["score"], -(r["count"] or 0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oa", required=True, help="path to an openaddresses checkout")
    ap.add_argument("--out", default="data/output/centerline_discovery.json")
    ap.add_argument("sources", nargs="+", help="OA source ids, e.g. us/ca/fresno")
    a = ap.parse_args()

    result = {}
    for sid in a.sources:
        src = json.load(open(os.path.join(a.oa, "sources", sid + ".json")))
        if src.get("layers", {}).get("centerlines"):
            result[sid] = {"status": "already has centerlines"}
            continue
        roots = {rest_root(l.get("data", "")) for ls in src.get("layers", {}).values() for l in ls}
        roots.discard(None)
        cands = [c for r in sorted(roots) for c in discover(r)]
        cands.sort(key=lambda r: (-r["score"], -(r["count"] or 0)))
        result[sid] = {"roots": sorted(roots), "candidates": cands[:5],
                       "proposed": {"name": next(l["name"] for ls in src["layers"].values() for l in ls),
                                    "data": cands[0]["url"], "protocol": "ESRI",
                                    "conform": cands[0]["conform"]} if cands else None}
        top = cands[0] if cands else None
        print(f"{sid:28} roots={len(roots)} candidates={len(cands)}"
              + (f"  best: {top['layer']} ({top['count']}) score={top['score']}" if top else ""), file=sys.stderr)

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(result, open(a.out, "w"), indent=2)
    print(a.out)





def _selftest():
    # Real field sets from Central Valley endpoints (Oct 2026).
    fresno = conform_for(["STR_ID", "STR_DIR", "STR_NAME", "STR_TYPE", "STR_POST_DIR"])
    assert fresno["name"]["fields"] == ["STR_DIR", "STR_NAME", "STR_TYPE", "STR_POST_DIR"], fresno
    nena = conform_for(["NGUID", "FromAddr_L", "ToAddr_L", "FromAddr_R", "ToAddr_R", "St_PreMod", "St_PreDir",
                        "St_PreTyp", "St_Name", "St_PosTyp", "St_PosDir", "St_PosMod", "LSt_Name", "PostCode_L", "PostCode_R"])
    assert nena["name"]["fields"] == ["St_PreMod", "St_PreDir", "St_PreTyp", "St_Name", "St_PosTyp", "St_PosDir", "St_PosMod"], nena
    assert (nena["id"], nena["addr_from_left"], nena["addr_to_right"], nena["zip_left"]) == ("NGUID", "FromAddr_L", "ToAddr_R", "PostCode_L"), nena
    kings = conform_for(["ID", "FULLNAME", "LADD_FR", "RADD_FR", "LADD_TO", "RADD_TO"])
    assert (kings["name"], kings["addr_from_left"], kings["addr_from_right"], kings["addr_to_right"]) == ("FULLNAME", "LADD_FR", "RADD_FR", "RADD_TO"), kings
    kern = conform_for(["SDIRPRE", "SFEANME", "SFEATYP", "SDIRSUF", "FRADDL", "TOADDL", "FRADDR", "TOADDR", "NAME_FULL"])
    assert kern["name"] == "NAME_FULL" and kern["addr_to_right"] == "TOADDR", kern
    visalia = conform_for(["CENTERLINEID", "FROMLEFT", "TOLEFT", "FROMRIGHT", "TORIGHT", "FULLNAME", "ZIPLEFT", "ZIPRIGHT"])
    assert visalia == {"format": "geojson", "id": "CENTERLINEID", "name": "FULLNAME", "addr_from_left": "FROMLEFT",
                       "addr_to_left": "TOLEFT", "addr_from_right": "FROMRIGHT", "addr_to_right": "TORIGHT",
                       "zip_left": "ZIPLEFT", "zip_right": "ZIPRIGHT"}, visalia
    assert not NOT_STREETS.search("REGIONAL_STREETS_VW") and NOT_STREETS.search("Street_Tree_Inventory")
    bak = conform_for(["LEFTFROM", "LEFTTO", "RIGHTFROM", "RIGHTTO", "PREFIX", "NAME", "SUFFIX", "TYPE"])
    assert bak["name"]["fields"] == ["PREFIX", "NAME", "TYPE", "SUFFIX"] and bak["addr_to_right"] == "RIGHTTO", bak
    print("selftest ok")


if __name__ == "__main__":
    _selftest() if sys.argv[1:] == ["--selftest"] else main()
