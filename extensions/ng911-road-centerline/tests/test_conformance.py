"""The five GERS Extension conformance rules, the NENA-STA-006.3 mandatory fields and coded domains,
and "the sample parses against the package".
Runs under pytest or as `python tests/test_conformance.py`."""

import json
import pathlib
import typing
from importlib.metadata import version

from packaging.specifiers import SpecifierSet
from pydantic import BaseModel, ValidationError

from overture.schema.transportation import RoadSegment
from overture.schema.system.ref import Id

from overture_ext_ng911_rcl import NENA_REQUIRED, REFERENCE_SCHEMA, STANDARD, TARGET, Ng911RoadCenterlineExtension, Ng911RoadCenterline

SAMPLE = pathlib.Path(__file__).parent.parent / "sample" / "ng911_road_centerline_sample.jsonl"


def test_1_targets_gers_enabled_feature_type():
    assert TARGET == (RoadSegment.model_fields["theme"].annotation.__args__[0], RoadSegment.model_fields["type"].annotation.__args__[0])
    assert RoadSegment.model_fields["id"].is_required()  # GERS-enabled: every segment carries an ID


def test_2_adds_properties_not_features():
    assert not {"geometry", "bbox", "theme", "type", "version"} & set(Ng911RoadCenterlineExtension.model_fields)


def test_3_joins_on_gers_id():
    field = Ng911RoadCenterlineExtension.model_fields["id"]
    assert field.is_required() and Id in (field.annotation, *typing.get_args(field.annotation))


def test_4_never_redefines_a_reference_property():
    top_level = set(Ng911RoadCenterlineExtension.model_fields) - {"id"}
    assert not top_level & set(RoadSegment.model_fields), top_level & set(RoadSegment.model_fields)
    assert all(issubclass(Ng911RoadCenterlineExtension.model_fields[f].annotation, BaseModel) for f in top_level)  # namespaced


def test_5_declares_reference_schema_range():
    assert version("overture-schema-theme-transportation") in SpecifierSet(REFERENCE_SCHEMA)


def test_nena_mandatory_fields_are_required():
    """Every field NENA-STA-006.3 makes mandatory for this layer is present and required in the package."""
    assert STANDARD == "NENA-STA-006.3-2026"
    for name in NENA_REQUIRED:
        assert name in Ng911RoadCenterline.model_fields and Ng911RoadCenterline.model_fields[name].is_required(), name


def test_coded_values_outside_nena_domains_are_rejected():
    """Street types must be NENA registry words: 'Avenue' parses, the abbreviation 'AVE' does not."""
    row = json.loads(SAMPLE.read_text().splitlines()[0])
    row["ng911"]["st_postyp"] = "Avenue"
    Ng911RoadCenterlineExtension.model_validate(row)
    row["ng911"]["st_postyp"] = "AVE"
    try:
        Ng911RoadCenterlineExtension.model_validate(row)
    except ValidationError:
        return
    raise AssertionError("'AVE' was accepted as a NENA street type")


def test_sample_parses():
    rows = [json.loads(line) for line in SAMPLE.read_text().splitlines()]
    assert rows
    for row in rows:
        Ng911RoadCenterlineExtension.model_validate(row)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
