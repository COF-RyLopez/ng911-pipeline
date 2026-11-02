# NG911 Railroad GERS Extension (prototype)

NENA NG9-1-1 **Railroad Centerline** properties (NENA-STA-006.3-2026) for Overture `transportation/segment`
features of the `rail` subtype, keyed on the segment's GERS ID. **Status: prototype.** Companion to
[`ng911-address`](../ng911-address) and [`ng911-road-centerline`](../ng911-road-centerline).

## Conformance

Same five rules and sample check as the other packages (`tests/test_conformance.py`): targets
`transportation/segment` (rail), adds properties not features, joins on `id`, keeps everything under `ng911`, and
declares `overture-schema-theme-transportation >=2.0,<3`.

## Properties (`ng911.*`, STA-006.3 Railroad Centerline names, lower-cased)

| Field | NENA | Source |
|---|---|---|
| `discrpagid`, `dateupdate`, `nguid` | DiscrpAgID, DateUpdate, NGUID (**mandatory**) | as in the other packages; NGUID `urn:emergency:uid:gis:RL:<GERS id>:<agency domain>` |
| `rlown` | RLOwn | FRA reporting mark (`UP`, `BNSF`, `SCAX` …) of the nearest line in FRA's North American Rail Network (BTS NTAD), within ~30 m of the segment's midpoint |
| `rlname` | RLName | Overture `names.primary` (e.g. "UP Fresno Subdivision") |
| `fra_arc_id` | (lineage, not NENA) | the matched FRA line's FRAARCID |
| `source_url` | (lineage, not NENA) | the OpenStreetMap way |

Not filled: **RLOp** (operator; trackage rights differ from ownership) and **RMPL/RMPH** (mileposts), which
aren't in open data. California rail segments only: the build drops track outside the state's counties.

## Why there's no hydrology package

NENA's Hydrology Line and Polygon layers would map to Overture's `base/water`, but base-theme IDs aren't stable
GERS IDs, so an Extension joined on them would break from release to release.
