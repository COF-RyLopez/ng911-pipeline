"""
The NG911 Road Centerline GERS Extension package: properties a 911 road centerline needs that the Overture
road `segment` doesn't carry (parsed street name, NENA road class, left/right address ranges and parity),
keyed on the segment's GERS ID.

It follows the same five GERS Extension conformance rules as the address package:
1. targets a GERS-enabled feature type: `transportation/segment` (road subtype) (TARGET);
2. adds properties, not features: no geometry, one row per existing segment;
3. joins on the GERS ID: `id`;
4. never redefines a reference property: everything sits in the `ng911` namespace; Overture's `names`
   becomes `ng911.st_predir` / `st_name` / `st_postyp`, its `class` becomes `ng911.roadclass`;
5. declares the reference schema range it was built against (REFERENCE_SCHEMA).

Field names follow NENA-STA-006.3-2026, Road Centerline layer, lower-cased (FromAddr_L -> fromaddr_l).
Coded fields are checked against NENA's domains (nena.py). Overture has no address ranges, so this prototype
derives them from the Overture addresses matched to each segment (same street name, within 50 m);
`addr_count_l/_r` say how many addresses each side's range rests on. A side with none is 0-0 with parity Z,
as NENA-STA-006.3 specifies.
"""

from typing import Annotated

from pydantic import BaseModel, Field

from overture.schema.system.model_constraint import no_extra_fields
from overture.schema.system.ref import Id

from .nena import Country, Parity, RoadClass, State, StreetNameDirectional, StreetNameType

TARGET = ("transportation", "segment")
REFERENCE_SCHEMA = ">=2.0,<3"  # overture-schema-theme-transportation versions this package was checked against
NENA_LAYER = "RoadCenterLine"
NENA_REQUIRED = ("discrpagid", "dateupdate", "nguid", "fromaddr_l", "toaddr_l", "fromaddr_r", "toaddr_r",
                 "parity_l", "parity_r", "st_name", "country_l", "country_r", "a1_l", "a1_r")  # mandatory in STA-006.3

AddressNumber = Annotated[int, Field(ge=0, le=999999)]


@no_extra_fields
class Ng911RoadCenterline(BaseModel):
    """NENA-STA-006.3 Road Centerline properties, plus the evidence behind the ranges and lineage."""

    # NENA mandatory
    discrpagid: Annotated[str, Field(description="Discrepancy Agency ID (DiscrpAgID).")]
    dateupdate: Annotated[str, Field(description="Date Updated (DateUpdate): W3C dateTime.")]
    nguid: Annotated[str, Field(description="NENA Globally Unique ID: urn:emergency:uid:gis:RCL:<GERS id>:<agency domain>.")]
    fromaddr_l: Annotated[AddressNumber, Field(description="Left from address (FromAddr_L); 0 when no addresses on that side.")]
    toaddr_l: Annotated[AddressNumber, Field(description="Left to address (ToAddr_L).")]
    fromaddr_r: Annotated[AddressNumber, Field(description="Right from address (FromAddr_R).")]
    toaddr_r: Annotated[AddressNumber, Field(description="Right to address (ToAddr_R).")]
    parity_l: Annotated[Parity, Field(description="Left parity (Parity_L): E, O, B, or Z for 0-0.")]
    parity_r: Annotated[Parity, Field(description="Right parity (Parity_R).")]
    st_name: Annotated[str, Field(description="Street name (St_Name), parsed from Overture's names.primary.")]
    country_l: Annotated[Country, Field(description="Left country (Country_L).")]
    country_r: Annotated[Country, Field(description="Right country (Country_R).")]
    a1_l: Annotated[State, Field(description="Left state (A1_L).")]
    a1_r: Annotated[State, Field(description="Right state (A1_R).")]
    # NENA optional
    st_predir: Annotated[StreetNameDirectional | None, Field(description="Street name pre-directional (St_PreDir).")] = None
    st_pretyp: Annotated[StreetNameType | None, Field(description="Street name pre type (St_PreTyp), e.g. 'Highway' in 'Highway 41'.")] = None
    st_postyp: Annotated[StreetNameType | None, Field(description="Street name post type (St_PosTyp), NENA registry word.")] = None
    a2_l: Annotated[str | None, Field(description="Left county (A2_L).")] = None
    a2_r: Annotated[str | None, Field(description="Right county (A2_R).")] = None
    postcode_l: Annotated[str | None, Field(description="Left postal code (PostCode_L): most common among left addresses.")] = None
    postcode_r: Annotated[str | None, Field(description="Right postal code (PostCode_R).")] = None
    postcomm_l: Annotated[str | None, Field(description="Left postal community (PostComm_L).")] = None
    postcomm_r: Annotated[str | None, Field(description="Right postal community (PostComm_R).")] = None
    roadclass: Annotated[RoadClass, Field(description="NENA RoadClass, mapped from Overture's class.")]
    # not NENA fields: the evidence behind the ranges and where the road comes from
    addr_count_l: Annotated[int, Field(ge=0, description="Addresses the left range rests on.")]
    addr_count_r: Annotated[int, Field(ge=0, description="Addresses the right range rests on.")]
    source_url: Annotated[str | None, Field(description="OpenStreetMap way to fix the road at the source.")] = None


@no_extra_fields
class Ng911RoadCenterlineExtension(BaseModel):
    """One row per Overture road segment: its GERS ID plus the `ng911` properties."""

    id: Annotated[Id, Field(description="GERS ID of the Overture road segment this row extends (the join key).")]
    ng911: Ng911RoadCenterline
