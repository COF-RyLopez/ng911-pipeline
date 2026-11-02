"""The five GERS Extension conformance rules, plus "the sample parses against the package".
Runs under pytest or as `python tests/test_conformance.py`."""

import json
import pathlib
import typing
from importlib.metadata import version

from packaging.specifiers import SpecifierSet
from pydantic import BaseModel

from overture.schema.addresses import Address
from overture.schema.system.ref import Id
from overture_ext_ng911 import REFERENCE_SCHEMA, TARGET, Ng911AddressExtension

SAMPLE = pathlib.Path(__file__).parent.parent / "sample" / "ng911_address_sample.jsonl"


def test_1_targets_gers_enabled_feature_type():
    assert TARGET == (Address.model_fields["theme"].annotation.__args__[0], Address.model_fields["type"].annotation.__args__[0])
    assert Address.model_fields["id"].is_required()  # GERS-enabled: every address carries an ID


def test_2_adds_properties_not_features():
    assert not {"geometry", "bbox", "theme", "type", "version"} & set(Ng911AddressExtension.model_fields)


def test_3_joins_on_gers_id():
    field = Ng911AddressExtension.model_fields["id"]
    assert field.is_required() and Id in (field.annotation, *typing.get_args(field.annotation))


def test_4_never_redefines_a_reference_property():
    top_level = set(Ng911AddressExtension.model_fields) - {"id"}
    assert not top_level & set(Address.model_fields), top_level & set(Address.model_fields)
    assert all(issubclass(Ng911AddressExtension.model_fields[f].annotation, BaseModel) for f in top_level)  # namespaced


def test_5_declares_reference_schema_range():
    assert version("overture-schema-theme-addresses") in SpecifierSet(REFERENCE_SCHEMA)


def test_sample_parses():
    rows = [json.loads(line) for line in SAMPLE.read_text().splitlines()]
    assert rows
    for row in rows:
        Ng911AddressExtension.model_validate(row)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
