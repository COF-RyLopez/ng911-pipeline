# Open-data NG9-1-1

Turning open address, road and boundary data into NENA NG9-1-1 GIS datasets for the 911 authorities of
the US and Canada, built mostly from each area's own government sources.

## Who's who

**Source agency**:
A government body that publishes a GIS layer this project reads, such as a city or county GIS office or a
state DOT.
_Avoid_: jurisdiction, data provider

**911 authority**:
The body responsible for the NG9-1-1 GIS dataset for an area, usually a county or regional 911 board and
in some states the state itself. It is the **Recipient** of one **Package** per county or census division it
covers.
_Avoid_: jurisdiction, PSAP, customer

**Recipient**:
The **911 authority** a **Package** is built for.
_Avoid_: client, subscriber

## What we produce

**Package**:
The NG9-1-1 dataset for one county (in Canada, one census division): every **Source agency**'s layers
inside it, reshaped to NENA, checked, and filled in with **Gap-fill candidates**. A **911 authority**
covering several gets several, shown together on its page.
_Avoid_: deliverable, ADMS, export

**Record**:
A feature that comes from a **Source agency**'s own current data. Where a Record exists it is the truth,
whatever Overture says.
_Avoid_: authoritative point

**Gap-fill candidate**:
A feature from Overture (or another open source) placed where no **Record** exists, offered for the
**Source agency** to accept or reject, never treated as a **Record**.
_Avoid_: suggestion, Overture point

**Review layer**:
Flags derived from OpenStreetMap-based data that point a **Source agency** at a place and say what to
check, never geometry or names to copy. Built only for an opted-in **Package**, given to that agency alone,
and kept apart from the **Records** and the public catalogue because of its license.
_Avoid_: OSM fixes

**Address UID**:
The one stable identifier of a real-world address across sources and Overture releases: the **Source
agency**'s own ID where it has one. NGUIDs are built from it; Overture GERS IDs hang off it.
_Avoid_: GERS ID (which changes), NGUID (which is derived from it)

## How agencies take part

**Opt-in**:
A **Source agency** or **911 authority** choosing, through the project's opt-in page, to receive its
**Package** or take one of the sharing paths (NAD submission, a clearer license, sharing with Overture or
Esri Community Maps).
_Avoid_: subscription, sign-up

**Sharing path**:
One of the routes a **Source agency** can take to publish its own data further: the NAD (through its
state address program, else nad@dot.gov), Overture (addresses through OpenAddresses), or Esri Community
Maps with sharing turned on (buildings, roads, boundaries). The agency takes the step; we prepare and
track it.
_Avoid_: submission (we never submit), distribution
