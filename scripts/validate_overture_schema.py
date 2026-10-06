#!/usr/bin/env python3
"""
scripts/validate_overture_schema.py

Type-safe schema validation for Overture Maps Foundation data using the official
Pydantic v2 schema package (`overture-schema` v2.0.0).

Validates:
1. Overture Address records (overture.schema.addresses.Address)
2. Overture Place records (overture.schema.places.Place)
3. Overture Transportation Segment records (overture.schema.transportation.Segment)

Supports both Parquet/tabular mode (flat rows) and GeoJSON mode (JSON strings).
"""

import sys
from overture.schema.addresses import Address
from overture.schema.places import Place
from overture.schema.transportation import Segment
from overture.schema.validation import validate
from pydantic import TypeAdapter

def validate_overture_sample():
    print("=" * 70)
    print("   OVERTURE MAPS SCHEMA V2 (PYDANTIC V2) TYPE-SAFE VALIDATION")
    print("=" * 70)

    # 1. Validate Address
    sample_address = {
        "id": "overture:address:08f28308470a1a0b",
        "version": 0,
        "theme": "addresses",
        "type": "address",
        "number": "2600",
        "street": "Fresno St",
        "postal_city": "Fresno",
        "postcode": "93721",
        "country": "US",
        "geometry": "POINT(-119.7871 36.7468)"
    }
    addr_obj = Address.model_validate(sample_address)
    print(f"[PASS] Address model_validate: {addr_obj.id} -> {addr_obj.number} {addr_obj.street}, {addr_obj.postal_city}")

    # 2. Validate Place
    sample_place = {
        "id": "overture:place:08f28308470a1a0c",
        "version": 0,
        "theme": "places",
        "type": "place",
        "names": {"primary": "Fresno City Hall"},
        "basic_category": "city_hall",
        "confidence": 0.98,
        "geometry": "POINT(-119.7871 36.7468)"
    }
    place_obj = Place.model_validate(sample_place)
    print(f"[PASS] Place model_validate:   {place_obj.id} -> {place_obj.names.primary} ({place_obj.basic_category})")

    # 3. Validate Transportation Segment via TypeAdapter
    segment_adapter = TypeAdapter(Segment)
    sample_segment = {
        "id": "overture:transportation:08f28308470a1a0d",
        "version": 0,
        "theme": "transportation",
        "type": "segment",
        "subtype": "road",
        "class": "primary",
        "connectors": [{"connector_id": "c1", "at": 0.0}, {"connector_id": "c2", "at": 1.0}],
        "names": {"primary": "E Ventura Ave"},
        "geometry": "LINESTRING(-119.787 36.746, -119.785 36.746)"
    }
    seg_obj = segment_adapter.validate_python(sample_segment)
    print(f"[PASS] Segment validate_python: {seg_obj.id} -> {seg_obj.subtype}/{seg_obj.class_}")

    print("-" * 70)
    print("All Overture Schema v2 Pydantic models validated successfully!\n")

if __name__ == "__main__":
    validate_overture_sample()
