"""
The NG911 GERS Extension package: properties a 911 address point needs that the Overture `address`
feature type doesn't carry, keyed on the address's GERS ID.

It follows the five GERS Extension conformance rules (Product Council, Oct 2026):
1. targets a GERS-enabled feature type: `addresses/address` (TARGET);
2. adds properties, not features: no geometry, one row per existing address;
3. joins on the GERS ID: `id`;
4. never redefines a reference property: everything else sits in the `ng911` namespace, including
   parsed versions of values Overture already has (its `street` becomes `ng911.st_name` + types);
5. declares the reference schema range it was built against (REFERENCE_SCHEMA).

Field names follow the NENA NG9-1-1 GIS Data Model, NENA-STA-006.3-2026, Site/Structure Address Point
layer, lower-cased (St_PosTyp -> st_postyp). Coded fields are checked against NENA's domains (nena.py):
street types and directionals are the NENA registry words ("Avenue", "North"), not abbreviations.
"""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

from overture.schema.system.model_constraint import no_extra_fields
from overture.schema.system.ref import Id

from .nena import Country, State, StreetNameDirectional, StreetNameType

TARGET = ("addresses", "address")
REFERENCE_SCHEMA = ">=2.0,<3"  # overture-schema-theme-addresses versions this package was checked against
NENA_LAYER = "SiteStructureAddressPoint"
NENA_REQUIRED = ("discrpagid", "dateupdate", "nguid", "country", "a1")  # mandatory in NENA-STA-006.3


class RoadMatch(str, Enum):
    """Whether a road with the address's street name runs near it (a basic NG911 MSAG-style check)."""

    OK = "OK"                        # same-named road within 50 m
    FAR = "FAR"                      # nearest same-named road is 50-400 m away
    NO_NAMED_ROAD = "NO_NAMED_ROAD"  # no road with this name within ~400 m


@no_extra_fields
class Ng911Address(BaseModel):
    """NENA-STA-006.3 Site/Structure Address Point properties, plus a road check and lineage."""

    # NENA mandatory
    discrpagid: Annotated[str, Field(description="Discrepancy Agency ID (DiscrpAgID): the agency domain that takes discrepancy reports.")]
    dateupdate: Annotated[str, Field(description="Date Updated (DateUpdate): W3C dateTime the record was created or last modified.")]
    nguid: Annotated[str, Field(description="NENA Globally Unique ID: urn:emergency:uid:gis:SSAP:<GERS id>:<agency domain>.")]
    country: Annotated[Country, Field(description="Country (Country), e.g. 'US'.")]
    a1: Annotated[State, Field(description="State (A1), two-letter code, e.g. 'CA'.")]
    # NENA optional
    a2: Annotated[str | None, Field(description="County (A2), as named in the Census Bureau list, e.g. 'Fresno County'.")] = None
    add_number: Annotated[int | None, Field(ge=0, le=999999, description="Address number (Add_Number).")] = None
    addnum_suf: Annotated[str | None, Field(description="Address number suffix (AddNum_Suf), e.g. '1/2', 'A'.")] = None
    st_predir: Annotated[StreetNameDirectional | None, Field(description="Street name pre-directional (St_PreDir), e.g. 'North'.")] = None
    st_pretyp: Annotated[StreetNameType | None, Field(description="Street name pre type (St_PreTyp), e.g. 'Highway' in 'Highway 41', 'Via' in 'Via Mariposa'.")] = None
    st_name: Annotated[str, Field(description="Street name (St_Name), parsed from Overture's street.")]
    st_postyp: Annotated[StreetNameType | None, Field(description="Street name post type (St_PosTyp), NENA registry word, e.g. 'Avenue'.")] = None
    st_posdir: Annotated[StreetNameDirectional | None, Field(description="Street name post-directional (St_PosDir), e.g. 'West' in 'Terra Vista Parkway West'.")] = None
    unit: Annotated[str | None, Field(description="Unit (Unit).")] = None
    post_comm: Annotated[str | None, Field(description="Postal community name (Post_Comm).")] = None
    post_code: Annotated[str | None, Field(description="Postal code (Post_Code).")] = None
    # not NENA fields: the road check and where the address comes from
    road_match: Annotated[RoadMatch, Field(description="Same-named road check against Overture transportation.")]
    road_distance_m: Annotated[float | None, Field(ge=0, description="Distance to the matched road, in metres.")] = None
    road_segment_id: Annotated[Id | None, Field(description="GERS ID of the matched transportation/segment.")] = None
    source_url: Annotated[str | None, Field(description="Where the address comes from, to fix it at the source.")] = None


@no_extra_fields
class Ng911AddressExtension(BaseModel):
    """One row per Overture address: its GERS ID plus the `ng911` properties."""

    id: Annotated[Id, Field(description="GERS ID of the Overture address this row extends (the join key).")]
    ng911: Ng911Address


NG911_FIELDS = list(Ng911Address.model_fields)
