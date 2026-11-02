# NG911 Road Centerline GERS Extension (prototype)

The companion to [`ng911-address`](../ng911-address): NENA NG9-1-1 Road Centerline properties for Overture
`transportation/segment` (road subtype), keyed on the segment's GERS ID. **Status: prototype.**

**Why.** A 911 Road Centerline layer (NENA-STA-006) is what call routing and geocoding run on: street name
in NENA parts, road class, and, most of all, **left/right address ranges with parity**. Overture roads have the
geometry and names but no address ranges. This package derives them from the Overture addresses already
matched to each segment.

## The two parts

| Part | What | Where |
|---|---|---|
| Package | Pydantic model `Ng911RoadCenterlineExtension` (this directory) | `pip install ./extensions/ng911-road-centerline` |
| Data | One row per named Overture road segment, joined on `id` | `extensions/ng911_road_centerline/ng911_road_centerline_ca.parquet` on the publisher's R2 bucket |

## Conformance

Same five rules and sample check as the address package, in `tests/test_conformance.py`: it targets
`transportation/segment`, adds properties not features, joins on `id`, keeps everything under `ng911` (Overture
`names` → `st_predir`/`st_pretyp`/`st_name`/`st_postyp`, `class` → `roadclass`), and declares
`overture-schema-theme-transportation >=2.0,<3`.

## Properties (`ng911.*`, NENA-STA-006.3-2026 Road Centerline names, lower-cased)

Coded fields hold NENA domain values (`overture_ext_ng911_rcl/nena_sta006_3_domains.json`, vendored from
NENA's GIS data model template); the model rejects anything else.

| Field | NENA | How |
|---|---|---|
| `discrpagid`, `dateupdate`, `nguid` | DiscrpAgID, DateUpdate, NGUID (**mandatory**) | as in the address package; NGUID `urn:emergency:uid:gis:RCL:<GERS id>:<agency domain>` |
| `fromaddr_l/_r`, `toaddr_l/_r` | FromAddr_L/R, ToAddr_L/R (**mandatory**) | from the addresses matched to the segment (same name, within 50 m), ordered along the segment's direction; 0–0 when a side has none |
| `parity_l/_r` | Parity_L/R (**mandatory**) | E, O, B, or Z for 0–0 |
| `st_name` | St_Name (**mandatory**) | Overture `names.primary`, parsed the same way as addresses |
| `country_l/_r`, `a1_l/_r` | Country_L/R, A1_L/R (**mandatory**) | `US`, `CA` |
| `st_predir`, `st_pretyp`, `st_postyp` | St_PreDir, St_PreTyp, St_PosTyp | NENA registry words: "North Blackstone Avenue" → North / BLACKSTONE / Avenue; "State Route 99" → State Route / 99 |
| `roadclass` | RoadClass | Overture class: motorway → Primary; trunk, primary, secondary → Secondary; tertiary, residential, unclassified, living_street → Local; service → Service Drive; track → Vehicular Trail |
| `a2_l/_r` | A2_L/R | the county the segment falls in |
| `postcode_l/_r`, `postcomm_l/_r` | PostCode_L/R, PostComm_L/R | most common among that side's addresses |
| `addr_count_l/_r` | (evidence, not NENA) | how many addresses each side's range rests on |
| `source_url` | (lineage, not NENA) | the OpenStreetMap way, to fix the road at the source |

**How sides are decided:** each matched address is projected onto its segment. The sign of the cross product
with the segment's direction at that point puts it on the left or the right. In a two-county test, 94% of sides
with 3 or more addresses came out purely even or purely odd. Of segments with addresses on both sides, 89% had
opposite parity, the usual US pattern.

## Limits of the prototype

- Ranges cover only the segments that matched addresses (mostly urban). They are **observed** ranges, not
  the theoretical ranges (e.g. 100–198) a county would publish.
- A segment crossing a county line is kept once, in the county with more of its addresses, and both sides take
  that county.
- One-way and speed limit already live on Overture's segment (`access_restrictions`, `speed_limits`), so
  they aren't repeated here (rule 4).
