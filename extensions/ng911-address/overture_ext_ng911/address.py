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

Field names follow the NENA NG9-1-1 GIS Data Model (NENA-STA-006), Site/Structure Address Point layer,
lower-cased (St_PreDir -> st_predir).
"""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

from overture.schema.system.model_constraint import no_extra_fields
from overture.schema.system.ref import Id

TARGET = ("addresses", "address")
REFERENCE_SCHEMA = ">=2.0,<3"  # overture-schema-theme-addresses versions this package was checked against


class RoadMatch(str, Enum):
    """Whether a road with the address's street name runs near it (a basic NG911 MSAG-style check)."""

    OK = "OK"                        # same-named road within 50 m
    FAR = "FAR"                      # nearest same-named road is 50-400 m away
    NO_NAMED_ROAD = "NO_NAMED_ROAD"  # no road with this name within ~400 m


@no_extra_fields
class Ng911Address(BaseModel):
    """NENA STA-006 Site/Structure Address Point properties."""

    nguid: Annotated[str, Field(description="NENA Globally Unique ID: urn:emergency:uid:gis:SSAP:<GERS id>:<agency domain>. "
                                             "The publisher's own ID, carried next to the GERS ID.")]
    add_number: Annotated[int | None, Field(description="Address number (Add_Number); null when not numeric.")] = None
    addnum_suf: Annotated[str | None, Field(description="Address number suffix (AddNum_Suf), e.g. '1/2', 'A'.")] = None
    st_predir: Annotated[str | None, Field(description="Street name pre-directional (St_PreDir), e.g. 'N'.")] = None
    st_name: Annotated[str, Field(description="Street name (St_Name), parsed from Overture's street.")]
    st_posttyp: Annotated[str | None, Field(description="Street name post type (St_PosTyp), USPS abbreviation, e.g. 'AVE'.")] = None
    unit: Annotated[str | None, Field(description="Unit (Unit).")] = None
    post_comm: Annotated[str | None, Field(description="Postal community name (Post_Comm).")] = None
    post_code: Annotated[str | None, Field(description="Postal code (Post_Code).")] = None
    county: Annotated[str, Field(description="County (County), e.g. 'Fresno County'.")]
    state: Annotated[str, Field(description="State (State), two-letter code.")]
    country: Annotated[str, Field(description="Country (Country), two-letter code.")]
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
