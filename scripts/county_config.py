"""County registry shared with dbt: the `counties` / `county` vars in dbt_project.yml."""
import os
import yaml

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(PROJECT_DIR, "dbt_project.yml")) as f:
    _vars = yaml.safe_load(f)["vars"]

COUNTIES = {str(k): v for k, v in _vars["counties"].items()}
DEFAULT_COUNTY = str(_vars["county"])


def get(fips=None):
    """Registry entry (with its 'fips') for a county; the dbt default when fips is None."""
    fips = str(fips or DEFAULT_COUNTY)
    if fips not in COUNTIES:
        raise SystemExit(f"county {fips} is not in the counties registry (dbt_project.yml); known: {', '.join(COUNTIES)}")
    return {"fips": fips, **COUNTIES[fips]}


def union_bbox():
    """[minx, miny, maxx, maxy] covering every registered county (one Overture fetch serves them all)."""
    boxes = [c["bbox"] for c in COUNTIES.values()]
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]
