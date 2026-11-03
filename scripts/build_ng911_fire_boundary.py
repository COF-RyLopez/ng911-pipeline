#!/usr/bin/env python3
"""
scripts/build_ng911_fire_boundary.py

A **candidate** NENA-STA-006.3 FirePolygon layer (a Primary Emergency Services boundary, REQUIRED in §4.3.2) for
California from two public CAL FIRE layers:
  1. California Local Fire Districts (671 districts, with FDIDs): the local agency where one is on file;
  2. Wildland Fire Direct Protection Areas (CAL FIRE / NIFC): outside the districts, the state or federal agency
     with wildland protection responsibility (CAL FIRE unit or contract county, USFS, NPS, BLM, ...).
Local DPA land outside every district is the gap and is reported, not filled.

It's a candidate, not the authority's layer: DPA is wildland responsibility (structure response there can differ),
district lines are a compilation CAL FIRE says isn't fully reviewed, and Agency_ID, ServiceURI and AVcard_URI are
assigned by each agency/911 authority, so they're left empty rather than invented.

Writes data/output/supplemental/ng911_fire/ng911_fire_boundary_candidate_ca.parquet (GeoParquet), manifest.json
and tiles/fire_boundary_candidate.pmtiles. Usage: python scripts/build_ng911_fire_boundary.py   (a few minutes)
"""
import datetime
import json
import os
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_ng911_extension import CALFIRE_DISTRICTS, PROJECT_DIR, TIGER_COUNTIES, load_places  # noqa: E402

DPA = ("https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/CA_WF_Direct_Protection_Areas_Public/"
       "FeatureServer/0/query?where=DPA_AGENCY%3C%3E%27LOCAL%27&outFields=DPA_AGENCY,NWCG_UNITID&outSR=4326"
       "&maxAllowableOffset=0.0001&f=geojson")
CONTRACT_COUNTIES = {"CAKRN": "Kern", "CALAC": "Los Angeles", "CAMRN": "Marin", "CAORC": "Orange",
                     "CASBC": "Santa Barbara", "CAVNC": "Ventura"}  # CAL FIRE contract counties run their own DPA
AGENCY = {"CDF": "CAL FIRE", "USF": "US Forest Service", "NPS": "National Park Service", "BLM": "Bureau of Land Management",
          "BIA": "Bureau of Indian Affairs", "UFW": "US Fish and Wildlife Service", "DOD": "Department of Defense",
          "NASA": "NASA"}
URN = "urn:emergency:service:responder.fire"
REQUIRED = ["discrpagid", "dateupdate", "nguid", "agency_id", "serviceuri", "serviceurn", "avcard_uri", "dsplayname"]
NOT_FILLED = ["agency_id", "serviceuri", "avcard_uri"]  # authority-assigned (FQDN / URIs); never derived


def display_name(agency, unit):
    if unit in CONTRACT_COUNTIES:
        return f"{CONTRACT_COUNTIES[unit]} County Fire (CAL FIRE contract county)"
    return f"{AGENCY.get(agency, agency)} ({unit})" if unit else AGENCY.get(agency, agency)


def main():
    updated = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    out = os.path.join(PROJECT_DIR, "data", "output", "supplemental", "ng911_fire")
    os.makedirs(out, exist_ok=True)
    c = duckdb.connect()
    c.sql("INSTALL spatial; LOAD spatial; SET geometry_always_xy = true;")
    load_places(c, "county", TIGER_COUNTIES, "BASENAME")
    load_places(c, "fire", CALFIRE_DISTRICTS, "Name", "FDID")
    load_places(c, "dpa", DPA, "DPA_AGENCY", "NWCG_UNITID")
    c.create_function("display_name", display_name, ["VARCHAR", "VARCHAR"], "VARCHAR", null_handling="special")  # unit can be NULL
    c.sql("CREATE TABLE ca AS SELECT ST_Union_Agg(ST_MakeValid(geom)) AS g FROM county")
    c.sql("CREATE TABLE fd_all AS SELECT ST_Union_Agg(geom) AS g FROM fire")
    # one polygon (set) per district and per wildland agency unit; the wildland part is what no district covers
    c.sql(f"""CREATE TABLE fb AS
        SELECT 'local_fire_district' AS basis, coalesce(min(name), 'Fire district ' || any_value(code)) AS dsplayname, any_value(code) AS fdid, NULL AS dpa_agency,
               NULL AS nwcg_unitid, 'FD-' || coalesce(any_value(code), left(md5(min(name)), 8)) AS local_id,
               ST_Union_Agg(geom) AS geom
        FROM fire GROUP BY coalesce(code, name)  -- one per FDID (a few FDIDs carry two spellings of a name)
        UNION ALL
        SELECT 'wildland_dpa', display_name(name, code), NULL, name, code, 'DPA-' || name || '-' || coalesce(code, 'NA'),
               ST_Intersection(ST_Difference(ST_Union_Agg(geom), (SELECT g FROM fd_all)), (SELECT g FROM ca))
        FROM dpa GROUP BY name, code""")
    c.sql("DELETE FROM fb WHERE ST_IsEmpty(geom) OR ST_Area(geom) < 1e-9")
    path = f"{out}/ng911_fire_boundary_candidate_ca.parquet"
    c.sql(f"""COPY (SELECT 'fire.ca.gov' AS discrpagid, '{updated}' AS dateupdate,
                     'urn:emergency:uid:gis:Fire:' || local_id || ':fire.ca.gov' AS nguid,
                     NULL::VARCHAR AS agency_id, NULL::VARCHAR AS serviceuri, '{URN}' AS serviceurn,
                     NULL::VARCHAR AS avcard_uri, left(dsplayname, 60) AS dsplayname,
                     true AS candidate, basis, fdid, dpa_agency, nwcg_unitid, geom AS geometry
              FROM fb ORDER BY basis, dsplayname) TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)""")

    n, ids, filled = c.execute(f"""SELECT count(*), count(DISTINCT nguid), count(*) FILTER (dsplayname IS NOT NULL)
                                 FROM '{path}'""").fetchall()[0]
    assert n == ids == filled, f"{n} rows, {ids} distinct NGUIDs, {filled} with a display name"
    # coverage of California's area (equal-area CRS), and the local-responsibility gap
    area = lambda g: f"ST_Area(ST_Transform({g}, 'EPSG:4326', 'EPSG:3310')) / 1e6"
    ca_km2, fd_km2, dpa_km2 = c.execute(f"""SELECT {area('(SELECT g FROM ca)')},
        {area('ST_Intersection((SELECT g FROM fd_all), (SELECT g FROM ca))')},
        (SELECT sum({area('geom')}) FROM fb WHERE basis = 'wildland_dpa')""").fetchall()[0]
    rows = dict(c.execute("SELECT basis, count(*) FROM fb GROUP BY 1").fetchall())
    by_agency = dict(c.execute(f"SELECT dpa_agency, round(sum({area('geom')})) FROM fb WHERE basis = 'wildland_dpa' GROUP BY 1 ORDER BY 2 DESC").fetchall())
    cov = {"california_km2": round(ca_km2), "local_fire_district_km2": round(fd_km2), "wildland_dpa_km2": round(dpa_km2),
           "covered_pct": round(100 * (fd_km2 + dpa_km2) / ca_km2, 1), "districts_only_pct": round(100 * fd_km2 / ca_km2, 1),
           "gap_local_no_district_km2": round(ca_km2 - fd_km2 - dpa_km2), "wildland_dpa_km2_by_agency": by_agency}
    print(f"[ng911_fire] {rows} polygons; California covered {cov['covered_pct']}% "
          f"(districts alone {cov['districts_only_pct']}%), gap {cov['gap_local_no_district_km2']:,} km²")
    manifest = {
        "dataset": "ng911-fire-boundary-candidate", "status": "prototype",
        "kind": "supplemental dataset (not a GERS Extension; service boundaries have no GERS feature type)",
        "candidate": "not the 911 authority's FirePolygon: local districts where on file, else the wildland Direct "
                     "Protection Area agency; structure response in DPA land can differ",
        "sources": {"local_fire_districts": CALFIRE_DISTRICTS.split("/query")[0] + " (CAL FIRE; not fully reviewed per its notes)",
                    "direct_protection_areas": DPA.split("/query")[0] + " (CAL FIRE / NIFC; CFMA agreement lines)"},
        "nena": {"standard": "NENA-STA-006.3-2026", "layer": "FirePolygon (§4.3.2, Table 4-5)", "required_fields": REQUIRED,
                 "filled": [f for f in REQUIRED if f not in NOT_FILLED], "not_filled": NOT_FILLED,
                 "not_filled_why": "Agency_ID is the agency's own FQDN, ServiceURI/AVcard_URI come from the ESInet; "
                                   "assigned by each agency or 911 authority, so left empty rather than invented"},
        "rows": rows, "coverage": cov, "generated_at": updated,
    }
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    tiles(c, out, path)


def tiles(c, out, path):
    """For an App 1 map layer later: PMTiles next to the data (same R2 part)."""
    import build_pmtiles as bp
    engine = bp.pick_engine()
    if engine is None:
        print("[WARNING] Neither tylertoo nor tippecanoe is installed; skipping the fire boundary map tiles.")
        return
    bp.build_layer(c, engine, "fire_boundary_candidate", path, "dsplayname AS Name, basis AS Basis, fdid AS FDID",
                   "geometry", ["-Z5", "-z12", "--coalesce-densest-as-needed"], f"{out}/tiles/fire_boundary_candidate.pmtiles",
                   attribution="CAL FIRE Local Fire Districts; CAL FIRE / NIFC Direct Protection Areas")


if __name__ == "__main__":
    main()
