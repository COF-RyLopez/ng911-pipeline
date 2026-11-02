"""NENA-STA-006.3-2026 coded domains (vendored from NENA's GIS data model template; source in the JSON),
as Pydantic types that reject any value outside the domain."""

import json
import pathlib
from typing import Annotated

from pydantic import AfterValidator

_DATA = json.loads((pathlib.Path(__file__).parent / "nena_sta006_3_domains.json").read_text())
STANDARD = _DATA["standard"]
DOMAINS = {name: frozenset(values) for name, values in _DATA["domains"].items()}


def _in(domain):
    def check(value):
        if value is not None and value not in DOMAINS[domain]:
            raise ValueError(f"{value!r} is not in the NENA {domain} domain ({STANDARD})")
        return value
    return AfterValidator(check)


StreetNameType = Annotated[str, _in("StreetNameType")]        # "Avenue", "Crescent", "State Route" (NENA registry)
StreetNameDirectional = Annotated[str, _in("StreetNameDirectional")]  # "North", "Southwest"
RoadClass = Annotated[str, _in("RoadClass")]
Parity = Annotated[str, _in("Parity")]                         # E, O, B, Z
Country = Annotated[str, _in("AdministrativeLevels0")]          # US
State = Annotated[str, _in("AdministrativeLevels1")]            # CA (ISO 3166-2 / USPS)
