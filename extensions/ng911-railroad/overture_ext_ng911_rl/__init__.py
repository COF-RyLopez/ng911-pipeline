"""NG911 Railroad GERS Extension (prototype): NENA-STA-006.3 Railroad Centerline properties for Overture rail segments.

Same five conformance rules as the address and road packages. Targets `transportation/segment` (rail subtype),
keyed on the segment's GERS ID; everything sits in the `ng911` namespace. Field names follow NENA-STA-006.3-2026,
Railroad Centerline layer, lower-cased (RLOwn -> rlown). The layer has no coded domains.
"""

from typing import Annotated

from pydantic import BaseModel, Field

from overture.schema.system.model_constraint import no_extra_fields
from overture.schema.system.ref import Id

STANDARD = "NENA-STA-006.3-2026"
TARGET = ("transportation", "segment")  # rail subtype
REFERENCE_SCHEMA = ">=2.0,<3"  # overture-schema-theme-transportation versions this package was checked against
NENA_LAYER = "RailroadCenterLine"
NENA_REQUIRED = ("discrpagid", "dateupdate", "nguid")  # mandatory in STA-006.3


@no_extra_fields
class Ng911Railroad(BaseModel):
    """NENA-STA-006.3 Railroad Centerline properties, plus lineage."""

    # NENA mandatory
    discrpagid: Annotated[str, Field(description="Discrepancy Agency ID (DiscrpAgID).")]
    dateupdate: Annotated[str, Field(description="Date Updated (DateUpdate): W3C dateTime.")]
    nguid: Annotated[str, Field(description="NENA Globally Unique ID: urn:emergency:uid:gis:RL:<GERS id>:<agency domain>.")]
    # NENA optional (RLOp and RMPL/RMPH aren't in open data, so the package leaves them out)
    rlown: Annotated[str | None, Field(description="Rail Line Owner (RLOwn): FRA reporting mark of the nearest FRA North American Rail Network line, e.g. 'UP', 'BNSF'.")] = None
    rlname: Annotated[str | None, Field(description="Rail Line Name (RLName), from Overture's names.primary, e.g. 'UP Fresno Subdivision'.")] = None
    # not NENA fields: lineage
    fra_arc_id: Annotated[str | None, Field(description="FRAARCID of the matched FRA rail line, to look it up in FRA's network.")] = None
    source_url: Annotated[str | None, Field(description="OpenStreetMap way, to fix the rail line at the source.")] = None


@no_extra_fields
class Ng911RailroadExtension(BaseModel):
    """One row per Overture rail segment: its GERS ID plus the `ng911` properties."""

    id: Annotated[Id, Field(description="GERS ID of the Overture rail segment this row extends (the join key).")]
    ng911: Ng911Railroad


__all__ = ["NENA_LAYER", "NENA_REQUIRED", "REFERENCE_SCHEMA", "STANDARD", "TARGET", "Ng911Railroad", "Ng911RailroadExtension"]
