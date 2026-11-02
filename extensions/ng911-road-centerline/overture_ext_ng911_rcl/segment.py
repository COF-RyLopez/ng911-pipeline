"""
The NG911 Road Centerline GERS Extension package: properties a 911 road centerline needs that the Overture
road `segment` doesn't carry (parsed street name, NENA road class, left/right address ranges and parity),
keyed on the segment's GERS ID.

It follows the same five GERS Extension conformance rules as the address package:
1. targets a GERS-enabled feature type: `transportation/segment` (road subtype) (TARGET);
2. adds properties, not features: no geometry, one row per existing segment;
3. joins on the GERS ID: `id`;
4. never redefines a reference property: everything sits in the `ng911` namespace; Overture's `names`
   becomes `ng911.st_predir` / `st_name` / `st_posttyp`, its `class` becomes `ng911.road_class`;
5. declares the reference schema range it was built against (REFERENCE_SCHEMA).

Field names follow the NENA NG9-1-1 GIS Data Model (NENA-STA-006), Road Centerline layer, lower-cased
(FromAddr_L -> fromaddr_l). Overture has no address ranges, so this prototype derives them from the
Overture addresses matched to each segment (same street name, within 50 m); `addr_count_l/_r` say how
many addresses each side's range rests on.
"""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

from overture.schema.system.model_constraint import no_extra_fields
from overture.schema.system.ref import Id

TARGET = ("transportation", "segment")
REFERENCE_SCHEMA = ">=2.0,<3"  # overture-schema-theme-transportation versions this package was checked against


class RoadClass(str, Enum):
    """NENA STA-006 RoadClass values this package emits (mapped from Overture's road class)."""

    PRIMARY = "Primary"                # motorway
    SECONDARY = "Secondary"            # trunk, primary, secondary
    LOCAL = "Local"                    # tertiary, residential, unclassified, living_street
    SERVICE_DRIVE = "Service Drive"    # service
    VEHICULAR_TRAIL = "Vehicular Trail"  # track
    OTHER = "Other"


class Parity(str, Enum):
    """NENA Parity_L / Parity_R."""

    EVEN = "E"
    ODD = "O"
    BOTH = "B"
    ZERO = "Z"  # no addresses on that side


Side = Annotated[int | None, Field(ge=0)]


@no_extra_fields
class Ng911RoadCenterline(BaseModel):
    """NENA STA-006 Road Centerline properties."""

    nguid: Annotated[str, Field(description="NENA Globally Unique ID: urn:emergency:uid:gis:RCL:<GERS id>:<agency domain>.")]
    st_predir: Annotated[str | None, Field(description="Street name pre-directional (St_PreDir).")] = None
    st_name: Annotated[str, Field(description="Street name (St_Name), parsed from Overture's names.primary.")]
    st_posttyp: Annotated[str | None, Field(description="Street name post type (St_PosTyp), USPS abbreviation.")] = None
    road_class: Annotated[RoadClass, Field(description="NENA RoadClass, mapped from Overture's class.")]
    fromaddr_l: Annotated[Side, Field(description="Left from address (FromAddr_L), derived from matched addresses.")] = None
    toaddr_l: Annotated[Side, Field(description="Left to address (ToAddr_L).")] = None
    fromaddr_r: Annotated[Side, Field(description="Right from address (FromAddr_R).")] = None
    toaddr_r: Annotated[Side, Field(description="Right to address (ToAddr_R).")] = None
    parity_l: Annotated[Parity, Field(description="Left parity (Parity_L).")]
    parity_r: Annotated[Parity, Field(description="Right parity (Parity_R).")]
    addr_count_l: Annotated[int, Field(ge=0, description="Addresses the left range rests on.")]
    addr_count_r: Annotated[int, Field(ge=0, description="Addresses the right range rests on.")]
    postcode_l: Annotated[str | None, Field(description="Left postal code (PostCode_L): most common among left addresses.")] = None
    postcode_r: Annotated[str | None, Field(description="Right postal code (PostCode_R).")] = None
    postcomm_l: Annotated[str | None, Field(description="Left postal community (PostComm_L).")] = None
    postcomm_r: Annotated[str | None, Field(description="Right postal community (PostComm_R).")] = None
    county_l: Annotated[str, Field(description="Left county (County_L).")]
    county_r: Annotated[str, Field(description="Right county (County_R).")]
    state_l: Annotated[str, Field(description="Left state (State_L).")]
    state_r: Annotated[str, Field(description="Right state (State_R).")]
    country_l: Annotated[str, Field(description="Left country (Country_L).")]
    country_r: Annotated[str, Field(description="Right country (Country_R).")]
    source_url: Annotated[str | None, Field(description="OpenStreetMap way to fix the road at the source.")] = None


@no_extra_fields
class Ng911RoadCenterlineExtension(BaseModel):
    """One row per Overture road segment: its GERS ID plus the `ng911` properties."""

    id: Annotated[Id, Field(description="GERS ID of the Overture road segment this row extends (the join key).")]
    ng911: Ng911RoadCenterline
