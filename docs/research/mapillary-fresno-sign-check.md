# Fresno County sign check with Mapillary detections: pilot plan

Status: plan, November 2026. Not built. Not legal advice.
Background: the national design note, open-ng911-addresses `docs/research/mapillary-detections.md`.

## Why Fresno can do this when the national pipeline can't

The national Packages are public, so Mapillary's terms rule its detections out there: no open licence, and
derived data may be published only into OSM or Overture, or under ODbL. This pilot is internal analysis for
Fresno County's own road data, and nothing from it is published. Mapillary's terms (s.12) allow commercial
and government use to improve your own maps and services, so the pilot stays inside these rules:

1. **Nothing published.** It is never part of `run_pilot.py`, CI or `publish_to_r2.py`. Outputs go to
   `data/private/` (git-ignored) and to county staff, never to R2, PMTiles, the hub apps or a commit.
2. **A check, not a feed.** The terms bar use "in connection with real-time navigation or route guidance", so
   detections never flow straight into `SpeedLimit` / `OneWay` or CAD routing. They produce a review list.
3. **Staff verify.** A row names a place and what to check. Once staff confirm (field visit, work order,
   or the imagery itself), the edit is the county's own record and goes into the NG911 layer as usual.
4. **Published interfaces only.** Map-feature vector tiles (`mly_map_feature_traffic_sign`,
   `mly_map_feature_point`) at z14, with a registered client token, like `fetch_mapillary_coverage.py`.
5. **Other agencies.** County-wide includes Clovis, Sanger, Reedley and the other cities. Checking their
   roads internally is the same use. Sending a list to one of them (place and what to check, no Mapillary
   content to copy) is the step to clear with counsel first, or under the Meta grant if it comes through.

## What it compares

| Detection (Mapillary value) | Compared with | Finding |
|---|---|---|
| `regulatory--maximum-speed-limit-NN--*` (R2-1) | `SpeedLimit` on the snapped segment and direction | Different value; no value on the segment; class default used where a sign is posted |
| `regulatory--one-way-*`, `regulatory--no-entry--*` (R6-1/2, R5-1) | `OneWay` | Sign says one-way, segment says B, or the direction is reversed |
| `regulatory--stop--*`, `regulatory--yield--*`, all-way plaque | Sign inventory, if one exists | Control at an intersection the inventory lacks, or vice versa |
| `regulatory--no-left-turn--*`, `--no-right-turn--*`, `--no-u-turn--*` | Nothing in the county layer yet | New candidate turn restriction (review only) |
| `object--fire-hydrant`, `object--traffic-light--*` | Hydrant and signal layers, if available | Present in imagery and not in the layer, or the reverse |

The first run compares against the road attributes the pipeline already has (`speed_mph` and `one_way` from
the county streets source). A sign inventory (county Public Works, City of Fresno traffic, Caltrans for
state routes) becomes the second comparison when we have one.

## Method

1. **Tiles.** z14 tiles covering the county's road centerlines (about 6,000 tiles for Fresno County's
   15,500 km², most of them empty foothill and mountain tiles that come back blank).
2. **Snap.** Same rules as the national note: segments within 20 m; travel bearing = facing + 180°,
   within 30° of the segment bearing (FT or TF); near an intersection, the approach whose end bearing
   matches; otherwise right-side rule. Unsnapped signs are counted by reason.
3. **Confidence.** A finding needs a detection seen in two or more images, and its last-seen date. Older
   than five years is listed as stale, not as a finding.
4. **Speed propagation.** A posted value applies downstream to the next speed sign, route change or a
   higher-class intersection. A finding is a mismatch on that run of segments, not on one segment.
5. **Output.** `data/private/mapillary_sign_check.gpkg` and a CSV: finding type, segment ID, direction,
   county value, what the sign suggests, sightings, last seen, and a Mapillary viewer link for staff.
   The summary prints counts by finding type and by city, and nothing goes to the build logs.

## What I need from Ryan

- A Mapillary client token registered for this purpose (the viewer's public token isn't meant for bulk
  feature pulls). It runs on your Mac: the cloud sandbox can't reach Mapillary.
- Whether the county or city has a sign inventory (Cartegraph, Cityworks or similar) we can read.
- Who at the county reviews the list, so the output is shaped for them.

## Success measure

Of a random sample of 100 findings that staff check, the share that turn out to be real (wrong or missing
`SpeedLimit` / `OneWay`, or a sign missing from the inventory). Above about 60%, it's worth a scheduled
quarterly run; below that, tighten the snapping and confidence rules before going on.
