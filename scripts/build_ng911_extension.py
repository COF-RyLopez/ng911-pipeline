#!/usr/bin/env python3
"""
scripts/build_ng911_extension.py

The data half of the NG911 GERS Extension prototypes, one dataset per package, built from the
Overture-only county builds. Each row is keyed on a GERS ID with NENA STA-006 properties in the `ng911`
namespace, and carries no geometry: consumers join on `id`.

  ng911_address         -> addresses/address        (package extensions/ng911-address)
  ng911_road_centerline -> transportation/segment   (package extensions/ng911-road-centerline)
  ng911_railroad        -> transportation/segment, rail subtype (package extensions/ng911-railroad)

Each writes data/output/extensions/<name>/:
  <name>_ca.parquet    the dataset
  <name>_sample.jsonl  a sample that parses against the package (also copied into the package)
  manifest.json        what a catalog listing reports: rows, field fill, and GERS ID coverage
                       (share of IDs that resolve in the stated Overture release)
Usage: python scripts/build_ng911_extension.py   (after overture_only_counties.py)
"""
import datetime
import glob
import json
import os
import shutil
import sys

import urllib.request

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from statewide_overture_scorecard import PROJECT_DIR, RELEASE, STATE_BBOX  # noqa: E402

BUILDS = os.path.join(PROJECT_DIR, "data", "output", "overture_only", "*")
OUT_ROOT = os.path.join(PROJECT_DIR, "data", "output", "extensions")
SAMPLE_PER_COUNTY = 5
COUNTY_KEY = "regexp_extract(filename, '/overture_only/([^/]+)/', 1)"
COUNTY_NAME = "array_to_string(list_transform(string_split(county_key, '_'), lambda w: upper(w[1]) || w[2:]), ' ') || ' County'"
ADD_NUMBER = "try_cast(nullif(regexp_extract(house_number, '^[0-9]+'), '') AS INTEGER)"
NENA_DOMAINS = os.path.join(PROJECT_DIR, "extensions", "ng911-address", "overture_ext_ng911", "nena_sta006_3_domains.json")

# NENA-STA-006.3 wants street types and directionals as the NENA registry words, not USPS abbreviations.
# Abbreviations the parse emits -> registry word; anything else is looked up in the registry itself, and a
# value in neither is left empty (and counted in the manifest) rather than guessed.
NENA_TYPE = {"ST": "Street", "AVE": "Avenue", "BLVD": "Boulevard", "RD": "Road", "DR": "Drive", "LN": "Lane",
             "WAY": "Way", "CT": "Court", "PL": "Place", "CIR": "Circle", "CV": "Cove", "HWY": "Highway",
             "PKWY": "Parkway", "TRL": "Trail", "LOOP": "Loop", "TER": "Terrace", "ALY": "Alley", "PLZ": "Plaza",
             "CRES": "Crescent", "CMN": "Common", "GLN": "Glen", "SQ": "Square", "PT": "Point", "WALK": "Walk",
             "RDG": "Ridge", "XING": "Crossing", "EXPY": "Expressway", "FWY": "Freeway", "PATH": "Path"}
NENA_DIR = {"N": "North", "S": "South", "E": "East", "W": "West",
            "NE": "Northeast", "NW": "Northwest", "SE": "Southeast", "SW": "Southwest"}
# Street name pre types ("Highway" in "Highway 41", "Via" in "Via Mariposa"). The English ones only before a
# number or single letter ("AVENUE 12", "AVENUE N"), the Spanish ones only when there's no post type, so a
# name like "CORTE MADERA AVE" keeps its name.
NENA_PRETYPE = {"UNITED STATES HIGHWAY": "United States Highway", "US HIGHWAY": "United States Highway",
                "US HWY": "United States Highway", "US": "United States Highway", "STATE HIGHWAY": "State Highway",
                "STATE HWY": "State Highway", "STATE ROUTE": "State Route", "SR": "State Route",
                "COUNTY ROAD": "County Road", "CR": "County Road", "INTERSTATE": "Interstate", "I": "Interstate",
                "HIGHWAY": "Highway", "HWY": "Highway", "AVENUE": "Avenue", "AVE": "Avenue", "ROUTE": "Route",
                "RTE": "Route", "CALLE": "Calle", "CAMINO": "Camino", "VIA": "Via", "PASEO": "Paseo",
                "AVENIDA": "Avenida", "CORTE": "Corte"}
SPANISH_PRETYPES = ("CALLE", "CAMINO", "VIA", "PASEO", "AVENIDA", "CORTE")
# A3 (NENA-STA-006.3 "Administrative Level 3", formerly Incorporated Municipality): the city a feature is in,
# from the state's CDTFA city boundaries (CA state geoportal, public domain; all 483 incorporated cities).
# Outside every city A3 stays empty: STA-006.3 has no "unincorporated" value, unincorporated communities are A4.
CDTFA_CITIES = ("https://services3.arcgis.com/uknczv4rpevve42E/arcgis/rest/services/"
                "California_Cities_and_Identifiers_Blue_Version_view/FeatureServer/2/query"
                "?where=1%3D1&outFields=CDTFA_CITY&outSR=4326&f=geojson")
# A4 ("Administrative Level 4", formerly Unincorporated Community): the Census Designated Place a feature is in,
# only where A3 is empty. CDPs (Census TIGERweb, public domain; 1,139 in CA) are the Census Bureau's statistical
# stand-in for named unincorporated communities. ponytail: CDP lines aren't the county's own community
# boundaries; swap in a county's community-plan areas where it publishes them.
CENSUS_CDPS = ("https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Places_CouSub_ConCity_SubMCD/"
               "MapServer/5/query?where=STATE%3D%2706%27&outFields=BASENAME&outSR=4326&f=geojson")
# Emergency service zone evidence (not NENA fields): the local fire district a feature is in, from CAL FIRE's
# statewide compilation (671 districts; generalized to ~10 m). ESN itself is assigned by each 911 authority to
# its own zones, so it is left empty rather than invented; the district name and FDID let an authority map to it.
CALFIRE_DISTRICTS = ("https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/California_Local_Fire_Districts/"
                     "FeatureServer/0/query?where=1%3D1&outFields=Name,FDID&outSR=4326&maxAllowableOffset=0.0001&f=geojson")


# Railroad owners: FRA's North American Rail Network (BTS NTAD, public domain), matched to Overture rail segments
NARN = ("https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_North_American_Rail_Network_Lines/"
        "FeatureServer/0/query?where=STATEAB%3D%27CA%27&outFields=FRAARCID,RROWNER1&outSR=4326&f=geojson")
TIGER_COUNTIES = ("https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query"
                  "?where=STATE%3D%2706%27&outFields=BASENAME&outSR=4326&maxAllowableOffset=0.0005&f=geojson")


def load_places(c, table, url, field, code=None):
    """Polygons from an ArcGIS geojson query as table <table>(name, code, geom); one request each (under the record limit)."""
    features, offset = [], 0
    while True:  # ArcGIS pages at its record limit (2,000 here); most layers fit in one page
        req = urllib.request.Request(f"{url}&resultOffset={offset}", headers={"User-Agent": "ng911-pipeline"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            page = json.load(resp)
        features += page["features"]
        offset += len(page["features"])
        if not page.get("exceededTransferLimit") and not page.get("properties", {}).get("exceededTransferLimit"):
            break
    c.execute(f"CREATE TABLE {table}_raw (name VARCHAR, code VARCHAR, gj VARCHAR)")
    c.executemany(f"INSERT INTO {table}_raw VALUES (?, ?, ?)",
                  [(f["properties"][field], (None if f["properties"].get(code) is None else str(f["properties"][code])), json.dumps(f["geometry"])) for f in features if f["geometry"]])
    c.sql(f"""CREATE TABLE {table} AS SELECT name, code, geom, ST_Area(geom) AS area
              FROM (SELECT name, code, ST_MakeValid(ST_GeomFromGeoJSON(gj)) AS geom FROM {table}_raw)""")
    print(f"  -> {len(features)} {table} parts, {c.execute(f'SELECT count(DISTINCT name) FROM {table}').fetchall()[0][0]} names")


def add_admin(c):
    """addr_city / seg_admin (small lookup tables, joined where used, not copied into the 13M-row addr):
    the city, else the CDP, and the fire district, each address and each segment's midpoint is in."""
    def admin(table, pts, key):
        def within(poly):  # inner spatial joins, so DuckDB plans them as spatial joins; the smallest polygon wins overlaps
            return f"""(SELECT p.{key}, arg_min(t.name, t.area) AS name, arg_min(t.code, t.area) AS code
                        FROM {pts} p JOIN {poly} t ON ST_Intersects(t.geom, p.pt) GROUP BY 1)"""
        c.sql(f"""CREATE TABLE {table} AS SELECT {key}, ci.name AS a3, CASE WHEN ci.name IS NULL THEN cd.name END AS a4,
                         fd.name AS fire_district, fd.code AS fire_fdid
                  FROM (SELECT DISTINCT {key} FROM {pts}) LEFT JOIN {within('city')} ci USING ({key})
                  LEFT JOIN {within('cdp')} cd USING ({key}) LEFT JOIN {within('fire')} fd USING ({key})""")
    admin("addr_city", "(SELECT overture_id, geom AS pt FROM addr)", "overture_id")
    admin("seg_admin", """(SELECT overture_segment_id AS sc_seg, ST_LineInterpolatePoint(geom, 0.5) AS pt FROM seg
                           WHERE ST_GeometryType(geom) = 'LINESTRING')""", "sc_seg")


def _case(col, mapping):
    return "CASE upper(" + col + ") " + " ".join(f"WHEN '{k}' THEN '{v}'" for k, v in mapping.items()) + " END"


def nena_setup(c):
    """Registry tables and macros the datasets map through."""
    domains = json.load(open(NENA_DOMAINS))["domains"]
    c.execute("CREATE TABLE nena_type AS SELECT unnest(?::VARCHAR[]) AS word", [domains["StreetNameType"]])
    c.sql("CREATE TABLE nena_type_abbr AS SELECT * FROM (VALUES " +
          ", ".join(f"('{k}', '{v}')" for k, v in NENA_TYPE.items()) + ") t(abbr, word)")
    c.sql("""CREATE MACRO nena_type_word(t) AS coalesce(
                 (SELECT word FROM nena_type_abbr WHERE abbr = upper(t)),
                 (SELECT word FROM nena_type WHERE upper(word) = upper(t)))""")
    c.sql(f"CREATE MACRO nena_dir_word(d) AS {_case('d', NENA_DIR)}")
    english = "|".join(k for k in sorted(NENA_PRETYPE, key=len, reverse=True) if k not in SPANISH_PRETYPES)
    spanish = "|".join(SPANISH_PRETYPES)
    # the pre type found at the start of a street name (raw), given its post type
    c.sql(f"""CREATE MACRO nena_pretype_raw(n, postyp) AS CASE
                 WHEN regexp_matches(n, '^({english}) +([0-9][0-9A-Z]*|[A-Z])$') THEN regexp_extract(n, '^({english}) +', 1)
                 WHEN postyp IS NULL AND regexp_matches(n, '^({spanish}) +[A-Z0-9]') THEN regexp_extract(n, '^({spanish}) +', 1)
              END""")
    c.sql(f"CREATE MACRO nena_pretype_word(raw) AS {_case('raw', NENA_PRETYPE)}")


# NENA Placement from OpenAddresses' per-source "accuracy" (1 rooftop, 2 parcel, 3 interpolated), where a source states one
OA_ACCURACY_PLACEMENT = {1: "Structure", 2: "Parcel", 3: "Geocoding"}


def load_oa_accuracy(c):
    """Table oa_accuracy(source_url, placement) from each OpenAddresses source file the addresses point to."""
    rows = []
    for (url,) in c.execute("SELECT DISTINCT source_url FROM addr WHERE source_url LIKE 'https://github.com/openaddresses/%'").fetchall():
        raw = url.replace("github.com/openaddresses/openaddresses/blob/", "raw.githubusercontent.com/openaddresses/openaddresses/")
        try:
            with urllib.request.urlopen(urllib.request.Request(raw, headers={"User-Agent": "ng911-pipeline"}), timeout=60) as r:
                layers = json.load(r).get("layers", {}).get("addresses", [])
        except Exception as e:  # one unreachable source leaves its addresses to the footprint test
            print(f"  [WARNING] {raw}: {e}")
            continue
        acc = next((l.get("conform", {}).get("accuracy") for l in layers if l.get("conform", {}).get("accuracy")), None)
        if acc in OA_ACCURACY_PLACEMENT:
            rows.append((url, OA_ACCURACY_PLACEMENT[acc]))
    c.execute("CREATE TABLE oa_accuracy (source_url VARCHAR, placement VARCHAR)")
    if rows:
        c.executemany("INSERT INTO oa_accuracy VALUES (?, ?)", rows)
    print(f"  -> {len(rows)} OpenAddresses sources state a placement accuracy")


def address_dataset(c, updated):
    cols = [r[0] for r in c.execute("DESCRIBE addr").fetchall()]
    has_unit = "unit" in cols  # carried once the parse keeps units
    in_building = "InBuilding" if "InBuilding" in cols else "NULL::BOOLEAN"  # builds before the footprint test lack it
    # ponytail: the agency domain is a placeholder (<county>.ca.gov) until a 9-1-1 authority publishes against this
    c.sql(f"""CREATE TABLE ext AS
        WITH a AS (SELECT *, nena_type_word(street_type) AS postyp,
                          nena_pretype_raw(street_name, nena_type_word(street_type)) AS pre_raw
                   FROM addr LEFT JOIN addr_city USING (overture_id)
                   LEFT JOIN (SELECT source_url, placement AS oa_placement FROM oa_accuracy) USING (source_url))
        SELECT overture_id AS id, county_key, street_type AS raw_postyp, struct_pack(
            discrpagid := county_key || '.ca.gov',
            dateupdate := '{updated}',
            nguid := 'urn:emergency:uid:gis:SSAP:' || overture_id || ':' || county_key || '.ca.gov',
            country := 'US',
            a1 := 'CA',
            a2 := {COUNTY_NAME},
            a3 := a3,
            a4 := a4,
            -- MSAG community candidate: the city, else the community, else the postal community (MSAG names are upper case)
            msagcomm := upper(coalesce(a3, a4, community_name)),
            add_number := {ADD_NUMBER},
            addnum_suf := nullif(trim(regexp_replace(house_number, '^[0-9]+', '')), ''),
            st_predir := nena_dir_word(pre_directional),
            st_pretyp := nena_pretype_word(pre_raw),
            st_name := CASE WHEN pre_raw IS NULL THEN street_name ELSE trim(street_name[length(pre_raw) + 1:]) END,
            st_postyp := postyp,
            st_posdir := nena_dir_word(post_directional),
            unit := {"nullif(trim(unit), '')" if has_unit else "NULL::VARCHAR"},
            post_comm := community_name,
            post_code := postcode,
            -- the source's stated method first; else on a structure if inside an Overture footprint
            placement := coalesce(oa_placement, CASE WHEN {in_building} THEN 'Structure' ELSE 'Unknown' END),
            fire_district := fire_district, fire_fdid := fire_fdid,
            road_match := RoadMatch,
            road_distance_m := DistanceM::DOUBLE,
            road_segment_id := RoadSegmentId,
            source_url := source_url) AS ng911
        FROM a""")


def road_centerline_dataset(c, updated):
    # Address ranges: each address matched to a segment (same name, within 50 m) lands on the left or right
    # of it (sign of the cross product with the segment's direction where the address projects onto it).
    # From/To follow the segment's digitized direction: numbers rising along it give From = min, To = max.
    c.sql(f"""CREATE TABLE side AS
        WITH p AS (
            SELECT a.RoadSegmentId AS seg_id, {ADD_NUMBER} AS n, a.postcode, a.community_name, ac.a3, ac.a4, ac.fire_district, ac.fire_fdid, a.geom AS pt,
                   s.geom AS line, ST_LineLocatePoint(s.geom, a.geom) AS f
            FROM addr a LEFT JOIN addr_city ac USING (overture_id) JOIN seg s ON s.overture_segment_id = a.RoadSegmentId AND s.county_key = a.county_key
            WHERE a.RoadMatch = 'OK' AND ST_GeometryType(s.geom) = 'LINESTRING'),
        d AS (
            SELECT *, ST_LineInterpolatePoint(line, greatest(f - 0.001, 0)) AS a0,
                      ST_LineInterpolatePoint(line, least(f + 0.001, 1)) AS a1
            FROM p WHERE n IS NOT NULL)
        SELECT seg_id, n, f, postcode, community_name, a3, a4, fire_district, fire_fdid,
               CASE WHEN (ST_X(a1) - ST_X(a0)) * (ST_Y(pt) - ST_Y(a0)) - (ST_Y(a1) - ST_Y(a0)) * (ST_X(pt) - ST_X(a0)) > 0
                    THEN 'L' ELSE 'R' END AS side
        FROM d""")
    c.sql("""CREATE TABLE rng AS
        SELECT seg_id, side, count(*) AS k,
               CASE WHEN coalesce(corr(n, f), 0) >= 0 THEN min(n) ELSE max(n) END AS from_n,
               CASE WHEN coalesce(corr(n, f), 0) >= 0 THEN max(n) ELSE min(n) END AS to_n,
               CASE WHEN bool_and(n % 2 = 0) THEN 'E' WHEN bool_and(n % 2 = 1) THEN 'O' ELSE 'B' END AS parity,
               mode(postcode) AS postcode, mode(community_name) AS postcomm, mode(a3) AS a3, mode(a4) AS a4,
               mode(fire_district) AS fire_district, mode(fire_fdid) AS fire_fdid
        FROM side GROUP BY ALL""")
    # ponytail: a segment crossing a county line is kept once, in the county where more of its addresses are,
    # and both sides take that county; per-side counties from the county polygons if border roads matter
    c.sql(f"""CREATE TABLE ext AS
        WITH s AS (SELECT *, nena_type_word(st_posttyp) AS postyp,
                          nena_pretype_raw(st_name, nena_type_word(st_posttyp)) AS pre_raw FROM seg)
        SELECT s.overture_segment_id AS id, s.county_key, s.st_posttyp AS raw_postyp, s.road_name, struct_pack(
            discrpagid := s.county_key || '.ca.gov',
            dateupdate := '{updated}',
            nguid := 'urn:emergency:uid:gis:RCL:' || s.overture_segment_id || ':' || s.county_key || '.ca.gov',
            -- NENA-STA-006.3: a side with no addresses is 0-0 with parity Z
            fromaddr_l := coalesce(l.from_n, 0), toaddr_l := coalesce(l.to_n, 0),
            fromaddr_r := coalesce(r.from_n, 0), toaddr_r := coalesce(r.to_n, 0),
            parity_l := coalesce(l.parity, 'Z'), parity_r := coalesce(r.parity, 'Z'),
            st_name := CASE WHEN s.pre_raw IS NULL THEN s.st_name ELSE trim(s.st_name[length(s.pre_raw) + 1:]) END,
            country_l := 'US', country_r := 'US', a1_l := 'CA', a1_r := 'CA',
            st_predir := nena_dir_word(s.st_predir),
            st_pretyp := nena_pretype_word(s.pre_raw),
            st_postyp := s.postyp,
            a2_l := {COUNTY_NAME}, a2_r := {COUNTY_NAME},
            -- a side's city from its addresses; with none, the city at the segment's midpoint
            a3_l := CASE WHEN l.k > 0 THEN l.a3 ELSE sc.a3 END, a3_r := CASE WHEN r.k > 0 THEN r.a3 ELSE sc.a3 END,
            a4_l := CASE WHEN l.k > 0 THEN (CASE WHEN l.a3 IS NULL THEN l.a4 END) ELSE sc.a4 END,
            a4_r := CASE WHEN r.k > 0 THEN (CASE WHEN r.a3 IS NULL THEN r.a4 END) ELSE sc.a4 END,
            msagcomm_l := upper(CASE WHEN l.k > 0 THEN coalesce(l.a3, l.a4, l.postcomm) ELSE coalesce(sc.a3, sc.a4) END),
            msagcomm_r := upper(CASE WHEN r.k > 0 THEN coalesce(r.a3, r.a4, r.postcomm) ELSE coalesce(sc.a3, sc.a4) END),
            fire_district_l := CASE WHEN l.k > 0 THEN l.fire_district ELSE sc.fire_district END,
            fire_district_r := CASE WHEN r.k > 0 THEN r.fire_district ELSE sc.fire_district END,
            fire_fdid_l := CASE WHEN l.k > 0 THEN l.fire_fdid ELSE sc.fire_fdid END,
            fire_fdid_r := CASE WHEN r.k > 0 THEN r.fire_fdid ELSE sc.fire_fdid END,
            postcode_l := l.postcode, postcode_r := r.postcode,
            postcomm_l := l.postcomm, postcomm_r := r.postcomm,
            roadclass := CASE WHEN s.road_class = 'motorway' THEN 'Primary'
                              WHEN s.road_class IN ('trunk', 'primary', 'secondary') THEN 'Secondary'
                              WHEN s.road_class IN ('tertiary', 'residential', 'unclassified', 'living_street') THEN 'Local'
                              WHEN s.road_class = 'service' THEN 'Service Drive'
                              WHEN s.road_class = 'track' THEN 'Vehicular Trail'
                              ELSE 'Other' END,
            addr_count_l := coalesce(l.k, 0)::INTEGER, addr_count_r := coalesce(r.k, 0)::INTEGER,
            source_url := s.osm_edit_url) AS ng911
        FROM s
        LEFT JOIN rng l ON l.seg_id = s.overture_segment_id AND l.side = 'L'
        LEFT JOIN rng r ON r.seg_id = s.overture_segment_id AND r.side = 'R'
        LEFT JOIN seg_admin sc ON sc.sc_seg = s.overture_segment_id
        WHERE s.st_name IS NOT NULL
        QUALIFY row_number() OVER (PARTITION BY s.overture_segment_id
                                   ORDER BY coalesce(l.k, 0) + coalesce(r.k, 0) DESC, s.county_key) = 1""")


def railroad_dataset(c, updated):
    # Overture rail segments statewide (not part of the county builds); owner from the nearest FRA rail line
    # within ~30 m of the segment's midpoint, county from the midpoint.
    xmin, ymin, xmax, ymax = STATE_BBOX["CA"]
    c.sql(f"""CREATE TABLE rail AS
        SELECT id, names.primary AS name, sources[1].record_id AS record_id, ST_LineInterpolatePoint(geometry, 0.5) AS pt
        FROM read_parquet('{RELEASE}/theme=transportation/type=segment/*.parquet', hive_partitioning=1)
        WHERE subtype = 'rail' AND bbox.xmin >= {xmin} AND bbox.xmax <= {xmax} AND bbox.ymin >= {ymin} AND bbox.ymax <= {ymax}
          AND ST_GeometryType(geometry) = 'LINESTRING'""")
    c.sql(f"""CREATE TABLE ext AS
        WITH fra AS (SELECT r.id, arg_min(n.name, ST_Distance(n.geom, r.pt)) AS owner, arg_min(n.code, ST_Distance(n.geom, r.pt)) AS arc
                     FROM rail r JOIN narn n ON ST_DWithin(n.geom, r.pt, 0.0003) GROUP BY 1),
             cty AS (SELECT r.id, any_value(lower(replace(t.name, ' ', '_'))) AS county_key
                     FROM rail r JOIN county t ON ST_Intersects(t.geom, r.pt) GROUP BY 1)
        SELECT r.id, cty.county_key, NULL::VARCHAR AS raw_postyp, struct_pack(
            discrpagid := cty.county_key || '.ca.gov',
            dateupdate := '{updated}',
            nguid := 'urn:emergency:uid:gis:RL:' || r.id || ':' || cty.county_key || '.ca.gov',
            rlown := fra.owner,
            rlname := r.name,
            fra_arc_id := fra.arc::VARCHAR,
            source_url := CASE WHEN regexp_matches(r.record_id, '^w[0-9]+')
                               THEN 'https://www.openstreetmap.org/way/' || regexp_extract(r.record_id, '^w([0-9]+)', 1) END
        ) AS ng911
        FROM rail r JOIN cty USING (id) LEFT JOIN fra USING (id)  -- California only: the bbox also catches NV, AZ, OR and MX track""")
    c.sql("DROP TABLE rail")


# NENA-STA-006.3 mandatory fields per layer (the packages assert the same lists in their conformance tests)
SSAP_REQUIRED = ("discrpagid", "dateupdate", "nguid", "country", "a1")
RCL_REQUIRED = ("discrpagid", "dateupdate", "nguid", "fromaddr_l", "toaddr_l", "fromaddr_r", "toaddr_r",
                "parity_l", "parity_r", "st_name", "country_l", "country_r", "a1_l", "a1_r")
RL_REQUIRED = ("discrpagid", "dateupdate", "nguid")

DATASETS = [
    # name, builder, package dir, release path for GERS coverage, target, reference schema package, NENA layer,
    # NENA mandatory fields, license note
    ("ng911_address", address_dataset, "ng911-address", "theme=addresses/type=address", "addresses/address",
     "overture-schema-theme-addresses", "SiteStructureAddressPoint", SSAP_REQUIRED,
     "Address values keep their source licenses (see ng911.source_url); road_* fields derive from Overture "
     "transportation, which is ODbL."),
    ("ng911_road_centerline", road_centerline_dataset, "ng911-road-centerline", "theme=transportation/type=segment",
     "transportation/segment", "overture-schema-theme-transportation", "RoadCenterLine", RCL_REQUIRED,
     "Road names and classes derive from Overture transportation (ODbL); address ranges derive from Overture "
     "addresses, which keep their source licenses."),
    ("ng911_railroad", railroad_dataset, "ng911-railroad", "theme=transportation/type=segment",
     "transportation/segment (rail)", "overture-schema-theme-transportation", "RailroadCenterLine", RL_REQUIRED,
     "Rail names derive from Overture transportation (ODbL); owners from FRA's North American Rail Network "
     "(public domain)."),
]


ADDR_ROAD_NOTES = {
    "coded_values": "street types, directionals, road class and parity are NENA domain values; "
        "checked by the package on every sample row",
    "a3_source": "CDTFA city boundaries (CA state geoportal), fetched at build time; empty outside cities",
    "a4_source": "Census Designated Places (Census TIGERweb), only where A3 is empty",
    "msagcomm_source": "candidate only: A3, else A4, else the postal community, upper-cased; the 911 authority's MSAG governs",
    "esn": "not filled: ESNs are assigned by each 911 authority; fire_district/fire_fdid (CAL FIRE local fire districts) are evidence for mapping to them",
    "placement_source": "OpenAddresses source accuracy where stated (1 Structure, 2 Parcel, 3 Geocoding); else Structure inside an Overture building footprint, else Unknown",
}
RAIL_NOTES = {
    "rlown_source": "FRA North American Rail Network (BTS NTAD) RROWNER1 reporting mark, from the FRA line nearest the segment's midpoint (within ~30 m)",
    "not_filled": "RLOp (operator) and RMPL/RMPH (mileposts): not in open data; trackage rights differ from ownership",
}


def write(c, name, package, release_path, target, schema_pkg, nena_layer, nena_required, license_note):
    out = os.path.join(OUT_ROOT, name)
    os.makedirs(out, exist_ok=True)
    c.sql(f"COPY (SELECT id, ng911 FROM ext ORDER BY county_key, id) TO '{out}/{name}_ca.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)")

    # sample: a few rows from every county, in the JSON the package parses
    sample = c.execute(f"""SELECT to_json(struct_pack(id := id, ng911 := ng911))::VARCHAR FROM (
        SELECT *, row_number() OVER (PARTITION BY county_key ORDER BY hash(id)) AS rn FROM ext)
        WHERE rn <= {SAMPLE_PER_COUNTY} ORDER BY county_key, id""").fetchall()
    sample_path = os.path.join(out, f"{name}_sample.jsonl")
    with open(sample_path, "w") as f:
        f.writelines(row[0] + "\n" for row in sample)
    pkg = os.path.join(PROJECT_DIR, "extensions", package)
    os.makedirs(os.path.join(pkg, "sample"), exist_ok=True)
    shutil.copy(sample_path, os.path.join(pkg, "sample"))

    # GERS ID coverage against the stated release (reported, not gated on)
    xmin, ymin, xmax, ymax = STATE_BBOX["CA"]
    total, resolved = c.execute(f"""
        WITH rel AS (SELECT id FROM read_parquet('{RELEASE}/{release_path}/*.parquet', hive_partitioning=1)
                     WHERE bbox.xmin BETWEEN {xmin} AND {xmax} AND bbox.ymin BETWEEN {ymin} AND {ymax})
        SELECT count(*), count(rel.id) FROM ext LEFT JOIN rel USING (id)""").fetchall()[0]
    fields = c.execute("SELECT json_keys(to_json(ng911)) FROM ext LIMIT 1").fetchall()[0][0]  # struct order
    fill = c.execute("SELECT " + ", ".join(f"round(100.0 * count(ng911.{f}) / count(*), 1)" for f in fields) + " FROM ext").fetchall()[0]
    # NENA marks: how many records carry every mandatory field, how full each NENA field is, and which raw
    # street types couldn't be mapped to a NENA registry word (left empty rather than guessed)
    all_required = " AND ".join(f"ng911.{f} IS NOT NULL" for f in nena_required)
    required_pct = c.execute(f"SELECT round(100.0 * count(*) FILTER (WHERE {all_required}) / count(*), 2) FROM ext").fetchall()[0][0]
    unmapped = [] if nena_layer == "RailroadCenterLine" else c.execute("""SELECT raw_postyp, count(*) n FROM ext WHERE raw_postyp IS NOT NULL AND ng911.st_postyp IS NULL
                            GROUP BY 1 ORDER BY 2 DESC LIMIT 10""").fetchall()
    manifest = {
        "extension": f"overture-extension-{package}",
        "package_version": "0.7.0",
        "status": "prototype",
        "target_feature_type": target,
        "join_key": "id (GERS ID)",
        "publisher_id_column": "ng911.nguid",
        "reference_schema": f"{schema_pkg} >=2.0,<3",
        "gers_id_coverage": {"release": RELEASE.rsplit("/", 1)[-1], "ids": total, "resolved": resolved,
                             "pct": round(100.0 * resolved / total, 2) if total else None},
        "rows": total,
        "counties": c.execute("SELECT count(DISTINCT county_key) FROM ext").fetchall()[0][0],
        "field_fill_pct": dict(zip(fields, fill)),
        "nena": {"standard": "NENA-STA-006.3-2026", "layer": nena_layer,
                 "mandatory_fields": list(nena_required),
                 "records_with_all_mandatory_fields_pct": required_pct,
                 **(RAIL_NOTES if nena_layer == "RailroadCenterLine" else
                    {**ADDR_ROAD_NOTES, "street_types_not_in_registry": dict(unmapped)})},
        "files": {"data": f"{name}_ca.parquet", "sample": f"{name}_sample.jsonl"},
        "license_note": license_note,  # ponytail: the license is the publisher's call
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"\n[{name}]", json.dumps({k: manifest[k] for k in ("rows", "counties", "gers_id_coverage")}))
    print("fill %:", manifest["field_fill_pct"])
    print("NENA:", json.dumps(manifest["nena"]))


def main():
    addr_files = glob.glob(os.path.join(BUILDS, "address_points.parquet"))
    if not addr_files:
        sys.exit(f"No Overture-only builds under {BUILDS}; run overture_only_counties.py first")
    c = duckdb.connect()
    # The 13.6M-row build spills ~9 GB of temp files. DuckDB capped that at 9.2 GiB on the CI runner (its
    # max_temp_directory_size), though the disk had ~80 GB free, so raise the cap; it's a ceiling, not a reservation.
    c.execute(f"SET max_temp_directory_size = '{os.environ.get('DUCKDB_MAX_TEMP', '40GiB')}'")
    c.sql("INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2'; SET geometry_always_xy = true; SET preserve_insertion_order = false;")
    c.sql(f"CREATE TABLE addr AS SELECT *, {COUNTY_KEY} AS county_key FROM read_parquet({addr_files!r}, filename = true, union_by_name = true)")
    c.sql(f"""CREATE TABLE seg AS SELECT *, {COUNTY_KEY} AS county_key
              FROM read_parquet({glob.glob(os.path.join(BUILDS, 'road_centerlines.parquet'))!r}, filename = true, union_by_name = true)""")
    nena_setup(c)
    load_places(c, "city", CDTFA_CITIES, "CDTFA_CITY")
    load_places(c, "cdp", CENSUS_CDPS, "BASENAME")
    load_places(c, "fire", CALFIRE_DISTRICTS, "Name", "FDID")
    load_places(c, "narn", NARN, "RROWNER1", "FRAARCID")
    load_places(c, "county", TIGER_COUNTIES, "BASENAME")
    add_admin(c)
    load_oa_accuracy(c)
    updated = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")  # DateUpdate: when built
    for name, build, *meta in DATASETS:
        build(c, updated)
        write(c, name, *meta)
        if name == "ng911_road_centerline":
            road_tiles(c)
        c.sql("DROP TABLE ext")


def road_tiles(c):
    """Map layer for App 1: every named Overture road with its derived address ranges, from the segment geometry."""
    import build_pmtiles as bp
    engine = bp.pick_engine()
    if engine is None:
        print("[WARNING] Neither tylertoo nor tippecanoe is installed; skipping the road range map tiles.")
        return
    src = os.path.join(OUT_ROOT, "ng911_road_centerline", "_map_layer.parquet")
    c.sql(f"""COPY (
        SELECT e.road_name AS Name,
               e.ng911.roadclass AS Class,
               CASE WHEN e.ng911.addr_count_l > 0 THEN e.ng911.fromaddr_l || '-' || e.ng911.toaddr_l || ' ' || e.ng911.parity_l END AS L,
               CASE WHEN e.ng911.addr_count_r > 0 THEN e.ng911.fromaddr_r || '-' || e.ng911.toaddr_r || ' ' || e.ng911.parity_r END AS R,
               e.ng911.addr_count_l AS LN, e.ng911.addr_count_r AS RN,
               e.ng911.addr_count_l + e.ng911.addr_count_r > 0 AS Ranged,
               s.geom
        FROM ext e JOIN seg s ON s.overture_segment_id = e.id AND s.county_key = e.county_key
    ) TO '{src}' (FORMAT PARQUET)""")
    bp.build_layer(c, engine, "overture_only_roads", src, "Name, Class, L, R, LN, RN, Ranged", "geom",
                   ["-Z10", "-z15", "--drop-densest-as-needed", "--extend-zooms-if-still-dropping"],
                   os.path.join(bp.TILES_DIR, "overture_only_road_centerlines.pmtiles"),
                   attribution="Overture Maps Foundation (OpenStreetMap, OpenAddresses); ranges derived from matched addresses")
    os.remove(src)  # ponytail: the map only needs the tiles; the dataset itself is the GeoParquet next to it


if __name__ == "__main__":
    main()
