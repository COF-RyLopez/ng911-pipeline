# NG911 GERS Extension (prototype)

A GERS Extension that adds NENA NG9-1-1 address-point properties to Overture `addresses/address`, built to
the GERS Extensions framework the Overture Product Council discussed in October 2026 (PC #40 and #41,
schema-wg #455). **Status: prototype**, for discussion in the schema working group.

**Why.** Every 911 authority in the US maintains a Site/Structure Address Point layer to the NENA NG9-1-1
GIS Data Model (NENA-STA-006). Overture addresses already cover most of it, but not in NENA's shape:
street names aren't split into pre-directional, name and post type, and there's no NENA ID, no check
against the road network, and no pointer back to the source. Today every 911 project redoes that work
against the reference. This Extension does it once, keyed on the GERS ID.

## The two parts

| Part | What | Where |
|---|---|---|
| Package | Pydantic model `Ng911AddressExtension` (this directory) | `pip install ./extensions/ng911-address` |
| Data | One row per Overture address, joined on `id` | `extensions/ng911_address/ng911_address_ca.parquet` on the publisher's R2 bucket |

```python
from overture_ext_ng911 import Ng911AddressExtension
row = Ng911AddressExtension.model_validate(json_row)   # id + ng911.{...}
```

## Conformance (the five rules, checked in `tests/test_conformance.py`)

1. **Targets a GERS-enabled feature type:** `addresses/address`.
2. **Adds properties, not features:** no geometry and no new rows; consumers join to Overture for the point.
3. **Joins on the GERS ID:** `id`.
4. **Never redefines a reference property:** everything lives under the `ng911` namespace, including parsed
   versions of values Overture already holds (Overture `street` → `ng911.st_predir` / `st_name` / `st_posttyp`).
5. **Declares a reference schema range:** `overture-schema-theme-addresses >=2.0,<3`.

Plus the listing requirement: `sample/ng911_address_sample.jsonl` parses against the package.

## Properties (`ng911.*`, NENA STA-006 names, lower-cased)

| Field | NENA | Source |
|---|---|---|
| `nguid` | NGUID | `urn:emergency:uid:gis:SSAP:<GERS id>:<agency domain>`: the publisher's own ID next to the GERS ID |
| `add_number`, `addnum_suf` | Add_Number, AddNum_Suf | Overture `number`, split ("1025 1/2" → 1025, "1/2") |
| `st_predir`, `st_name`, `st_posttyp` | St_PreDir, St_Name, St_PosTyp | Overture `street`, parsed and USPS-abbreviated |
| `unit` | Unit | Overture `unit` |
| `post_comm`, `post_code` | Post_Comm, Post_Code | Overture `address_levels` / `postcode` |
| `county`, `state`, `country` | County, State, Country | location |
| `road_match`, `road_distance_m`, `road_segment_id` | (validation) | nearest same-named Overture `transportation/segment` within ~400 m: `OK` ≤ 50 m, `FAR`, `NO_NAMED_ROAD`; the segment's GERS ID |
| `source_url` | (lineage) | the OpenAddresses source to fix upstream |

`road_segment_id` is itself a GERS ID, so the Extension links two reference themes, addresses and roads.

## Listing metadata (`manifest.json`, written with every data release)

GERS ID coverage is **reported, not gated**: the share of `id`s that resolve in the stated release
(currently `2026-09-23.1`), along with rows, counties and per-field fill rates.

## Open questions for the working group

- **Namespacing:** one `ng911` struct column (as here) or prefixed flat columns (`ng911_st_name`)?
- **Agency domain in `nguid`:** NENA expects the 911 authority's domain. The prototype uses a
  placeholder (`<county>.ca.gov`) until an authority publishes against the package.
- **More 911 layers:** Road Centerline (the same pattern on `transportation/segment`, adding address
  ranges and parity) is the obvious next package. Service boundaries (PSAP, fire, EMS, police) have no GERS
  feature type, so under the narrower definition they'd be a supplemental dataset rather than an Extension.
- **ID churn:** this dataset is rebuilt from each release, so joins stay current. A county publishing
  its own NG911 data against the package would need the changelog workflow.
- **License:** address values keep their source licenses (`source_url`), and `road_*` derives from Overture
  transportation (ODbL). Which license should the published dataset declare?
