"""The five GERS Extension conformance rules, the NENA-STA-006.3 mandatory fields, and "the sample parses".
Runs under pytest or as `python tests/test_conformance.py`."""

import json
import pathlib
import typing
from importlib.metadata import version

from packaging.specifiers import SpecifierSet
from pydantic import BaseModel, ValidationError

from overture.schema.transportation import RailSegment
from overture.schema.system.ref import Id

from overture_ext_ng911_rl import NENA_REQUIRED, REFERENCE_SCHEMA, STANDARD, TARGET, Ng911Railroad, Ng911RailroadExtension

SAMPLE = pathlib.Path(__file__).parent.parent / "sample" / "ng911_railroad_sample.jsonl"


def test_1_targets_gers_enabled_feature_type():
    assert TARGET == (RailSegment.model_fields["theme"].annotation.__args__[0], RailSegment.model_fields["type"].annotation.__args__[0])
    assert RailSegment.model_fields["id"].is_required()


def test_2_adds_properties_not_features():
    assert not {"geometry", "bbox", "theme", "type", "version"} & set(Ng911RailroadExtension.model_fields)


def test_3_joins_on_gers_id():
    field = Ng911RailroadExtension.model_fields["id"]
    assert field.is_required() and Id in (field.annotation, *typing.get_args(field.annotation))


def test_4_never_redefines_a_reference_property():
    top_level = set(Ng911RailroadExtension.model_fields) - {"id"}
    assert not top_level & set(RailSegment.model_fields)
    assert all(issubclass(Ng911RailroadExtension.model_fields[f].annotation, BaseModel) for f in top_level)


def test_5_declares_reference_schema_range():
    assert version("overture-schema-theme-transportation") in SpecifierSet(REFERENCE_SCHEMA)


def test_nena_mandatory_fields_are_required():
    assert STANDARD == "NENA-STA-006.3-2026"
    for name in NENA_REQUIRED:
        assert name in Ng911Railroad.model_fields and Ng911Railroad.model_fields[name].is_required(), name


def test_unknown_fields_are_rejected():
    row = json.loads(SAMPLE.read_text().splitlines()[0])
    row["ng911"]["rlop"] = "made up"
    try:
        Ng911RailroadExtension.model_validate(row)
    except ValidationError:
        return
    raise AssertionError("an undeclared field was accepted")


def test_sample_parses():
    rows = [json.loads(line) for line in SAMPLE.read_text().splitlines()]
    assert rows
    for row in rows:
        Ng911RailroadExtension.model_validate(row)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
