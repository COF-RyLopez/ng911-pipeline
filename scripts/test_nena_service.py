#!/usr/bin/env python3
"""
scripts/test_nena_service.py

Unit and integration test suite for NENA STA-005.1.2 ECRF/LVF REST API microservice.
"""

import sys
import os
from fastapi.testclient import TestClient

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nena_ecrf_lvf_service import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["nena_standard"] == "NENA STA-005.1.2 (ECRF/LVF)"
    print("[PASS] GET /health returned 200 HEALTHY")

def test_capabilities():
    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert "urn:service:sos.psap" in data["supported_service_urns"]
    print("[PASS] GET /v1/capabilities returned 200 with supported URNs")

def test_find_location_valid():
    payload = {
        "civic_address": {
            "house_number": "2600",
            "street_name": "FRESNO",
            "street_type": "ST",
            "community_name": "FRESNO",
            "state": "CA",
            "postcode": "93721"
        }
    }
    response = client.post("/v1/findLocation", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) > 0
    res = data["results"][0]
    assert res["validation_status"] in ["VALID", "VALID_WITH_ALIASING"]
    assert res["longitude"] is not None
    assert res["latitude"] is not None
    print(f"[PASS] POST /v1/findLocation returned {res['validation_status']} for 2600 FRESNO ST ({res['longitude']}, {res['latitude']})")

def test_find_location_invalid():
    payload = {
        "civic_address": {
            "house_number": "999999",
            "street_name": "NONEXISTENT_ROAD_XYZ",
            "state": "CA"
        }
    }
    response = client.post("/v1/findLocation", json=payload)
    assert response.status_code == 200
    data = response.json()
    res = data["results"][0]
    assert res["validation_status"] == "INVALID"
    assert "UNPROVISIONABLE_RECORD" in res["discrepancy_codes"]
    print("[PASS] POST /v1/findLocation returned INVALID with UNPROVISIONABLE_RECORD for non-existent address")

def test_get_route_by_coordinates():
    payload = {
        "service_urn": "urn:service:sos.psap",
        "location": {
            "longitude": -119.784,
            "latitude": 36.737
        }
    }
    response = client.post("/v1/getRoute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "route" in data
    route = data["route"]
    assert "urn:emergency:uid:psap" in route["primary_psap_uri"]
    assert route["psap_name"] is not None
    print(f"[PASS] POST /v1/getRoute returned primary PSAP: {route['psap_name']} ({route['primary_psap_uri']})")

if __name__ == "__main__":
    print("======================================================================")
    print("   NENA STA-005.1.2 ECRF/LVF MICROSERVICE TEST SUITE")
    print("======================================================================")
    test_health()
    test_capabilities()
    test_find_location_valid()
    test_find_location_invalid()
    test_get_route_by_coordinates()
    print("----------------------------------------------------------------------")
    print("All NENA STA-005.1.2 microservice unit tests passed!")
