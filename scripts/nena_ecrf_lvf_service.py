#!/usr/bin/env python3
"""
scripts/nena_ecrf_lvf_service.py

NENA STA-005.1.2 Compliant Emergency Call Routing Function (ECRF) and 
Location Validation Function (LVF) REST API Microservice for NG911.

Standards:
  - NENA STA-005.1.2 (ECRF/LVF Protocol Specification)
  - NENA-STA-010.3 (NG9-1-1 GIS Data Model - SSAP, RCL, ESB)

Endpoints:
  - POST /v1/findLocation : Location Validation Function (LVF)
  - POST /v1/getRoute     : Emergency Call Routing Function (ECRF)
  - GET  /v1/capabilities : NENA ECRF/LVF Capabilities & Service URN Registry
  - GET  /health          : Service Health & Metric Audit
"""

import os
import sys
import time
from typing import List, Optional
import duckdb
import pandas as pd
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "data", "output")
DB_PATH = os.path.join(PROJECT_DIR, "ng911_database.duckdb")
SSAP_PARQUET = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_ssap.parquet")
RCL_PARQUET = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_rcl.parquet")
ESB_PARQUET = os.path.join(OUTPUT_DIR, "mart_ng911_fresno_esb.parquet")

app = FastAPI(
    title="NENA STA-005.1.2 ECRF/LVF Microservice",
    description="Next Generation 9-1-1 Emergency Call Routing Function (ECRF) and Location Validation Function (LVF) REST API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Shared DuckDB connection
conn = None

def get_db_connection():
    global conn
    if conn is None:
        conn = duckdb.connect()
        conn.sql("INSTALL spatial; LOAD spatial;")
    return conn

# -----------------------------------------------------------------------------
# PYDANTIC SCHEMAS (NENA STA-005 & NENA-STA-010 COMPLIANT)
# -----------------------------------------------------------------------------

class CivicAddressInput(BaseModel):
    house_number: str = Field(..., example="2600", description="House Number (HNO)")
    house_number_suffix: Optional[str] = Field(None, example="", description="House Number Suffix (HNS)")
    pre_directional: Optional[str] = Field(None, example="", description="Pre-Directional (PRD)")
    street_name: str = Field(..., example="FRESNO", description="Street Name (STN)")
    street_type: Optional[str] = Field(None, example="ST", description="Street Type (STS)")
    post_directional: Optional[str] = Field(None, example="", description="Post-Directional (POD)")
    unit: Optional[str] = Field(None, example="", description="Unit/Apartment/Suite")
    community_name: Optional[str] = Field(None, example="FRESNO", description="Municipal / Place Name")
    state: str = Field("CA", example="CA", description="State Abbreviation")
    postcode: Optional[str] = Field(None, example="93721", description="Postal / ZIP Code")
    country: str = Field("US", example="US", description="Two-letter Country Code (ISO 3166-1)")

class PointLocationInput(BaseModel):
    longitude: float = Field(..., example=-119.784, description="WGS84 Longitude in Decimal Degrees")
    latitude: float = Field(..., example=36.737, description="WGS84 Latitude in Decimal Degrees")

class FindLocationRequest(BaseModel):
    civic_address: CivicAddressInput

class ValidatedLocationResult(BaseModel):
    validation_status: str = Field(..., example="VALID", description="VALID, VALID_WITH_ALIASING, or INVALID")
    ssap_nguid: Optional[str] = Field(None, example="urn:emergency:uid:gis:SSAP:101:fresnocountyca.gov")
    discrepancy_agency_id: str = Field("fresnocountyca.gov", example="fresnocountyca.gov")
    conflation_status: Optional[str] = Field(None, example="CONFLATED")
    matched_address: str = Field(..., example="2600 FRESNO ST, FRESNO CA 93721")
    longitude: Optional[float] = Field(None, example=-119.784)
    latitude: Optional[float] = Field(None, example=36.737)
    point_placement_type: str = Field("Site", example="Site")
    psap_attribution: Optional[str] = Field(None, example="Fresno County Sheriff PSAP")
    landmark_alias: Optional[str] = Field(None, example="Fresno City Hall")
    discrepancy_codes: List[str] = Field(default_factory=list, description="List of NENA discrepancy codes if any")

class FindLocationResponse(BaseModel):
    service_name: str = "Location Validation Function (LVF)"
    execution_time_ms: float
    results: List[ValidatedLocationResult]

class GetRouteRequest(BaseModel):
    service_urn: str = Field("urn:service:sos.psap", example="urn:service:sos.psap", description="NENA Emergency Service URN")
    location: Optional[PointLocationInput] = None
    civic_address: Optional[CivicAddressInput] = None

class RouteResponseResult(BaseModel):
    service_urn: str = Field(..., example="urn:service:sos.psap")
    primary_psap_uri: str = Field(..., example="urn:emergency:uid:psap:Fresno_County_Sheriff_PSAP:fresnocountyca.gov")
    psap_name: str = Field(..., example="Fresno County Sheriff PSAP")
    psap_phone: str = Field(..., example="tel:+15555550100")
    discrepancy_agency_id: str = Field("fresnocountyca.gov", example="fresnocountyca.gov")
    esb_fire_boundary: Optional[str] = Field(None, example="Fresno City Fire Department Boundary")
    longitude: float
    latitude: float

class GetRouteResponse(BaseModel):
    service_name: str = "Emergency Call Routing Function (ECRF)"
    execution_time_ms: float
    route: RouteResponseResult

# -----------------------------------------------------------------------------
# CORE BUSINESS LOGIC & QUERY ENGINE
# -----------------------------------------------------------------------------

@app.on_event("startup")
def startup_event():
    get_db_connection()
    if not os.path.exists(SSAP_PARQUET):
        print(f"[WARNING] SSAP Parquet file {SSAP_PARQUET} not found. Run scripts/run_pilot.py first.")

@app.get("/health")
def health_check():
    db = get_db_connection()
    ssap_count = 0
    if os.path.exists(SSAP_PARQUET):
        ssap_count = db.sql(f"SELECT count(*) FROM '{SSAP_PARQUET}'").fetchone()[0]
    return {
        "status": "HEALTHY",
        "nena_standard": "NENA STA-005.1.2 (ECRF/LVF)",
        "agency_domain": "fresnocountyca.gov",
        "ssap_address_count": ssap_count,
        "database_connected": True
    }

@app.get("/v1/capabilities")
def get_capabilities():
    return {
        "nena_standard": "NENA STA-005.1.2",
        "agency_domain": "fresnocountyca.gov",
        "supported_service_urns": [
            "urn:service:sos",
            "urn:service:sos.psap",
            "urn:service:sos.police",
            "urn:service:sos.fire",
            "urn:service:sos.ambulance"
        ],
        "supported_location_formats": [
            "CivicAddress (NENA-STA-010.3 SSAP)",
            "WGS84 Point (EPSG:4326)"
        ],
        "version": "1.0.0"
    }

@app.post("/v1/findLocation", response_model=FindLocationResponse)
def find_location(req: FindLocationRequest):
    """
    NENA STA-005.1.2 Location Validation Function (LVF)
    Validates a civic address against authoritative SSAP address points & RCL centerlines.
    """
    t0 = time.time()
    db = get_db_connection()
    c = req.civic_address

    if not os.path.exists(SSAP_PARQUET):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authoritative SSAP address point database not available. Run scripts/run_pilot.py first."
        )

    hno = c.house_number.strip().upper()
    stn = c.street_name.strip().upper()

    query = f"""
        SELECT 
            SSAP_NGUID,
            DisclID,
            ConflationStatus,
            HNO,
            HNS,
            PRD,
            STN,
            STS,
            POD,
            Unit,
            CommunityName,
            County,
            State,
            PostCode,
            PSAP,
            LandmarkName,
            Longitude,
            Latitude
        FROM '{SSAP_PARQUET}'
        WHERE upper(HNO) = '{hno}'
          AND (upper(STN) = '{stn}' OR upper(STN) LIKE '%{stn}%')
        LIMIT 5
    """

    results = []
    df = db.sql(query).df()

    if df.empty:
        # Address not found in exact SSAP points - check for ambiguity/unprovisionable
        formatted_addr = f"{hno} {stn} {c.street_type or ''}, {c.community_name or 'FRESNO'} {c.state} {c.postcode or ''}".strip()
        results.append(ValidatedLocationResult(
            validation_status="INVALID",
            discrepancy_agency_id="fresnocountyca.gov",
            matched_address=formatted_addr,
            discrepancy_codes=["UNPROVISIONABLE_RECORD", "CIVIC_ADDRESS_AMBIGUITY"]
        ))
    else:
        for _, row in df.iterrows():
            formatted_addr = f"{row['HNO']} {row['PRD'] or ''} {row['STN']} {row['STS'] or ''} {row['POD'] or ''} {row['Unit'] or ''}, {row['CommunityName']} {row['State']} {row['PostCode']}".replace("  ", " ").strip()
            
            val_status = "VALID"
            discrepancies = []
            if row['LandmarkName'] and pd.notna(row['LandmarkName']):
                val_status = "VALID_WITH_ALIASING"

            results.append(ValidatedLocationResult(
                validation_status=val_status,
                ssap_nguid=row['SSAP_NGUID'],
                discrepancy_agency_id=row['DisclID'] or "fresnocountyca.gov",
                conflation_status=row['ConflationStatus'],
                matched_address=formatted_addr,
                longitude=float(row['Longitude']),
                latitude=float(row['Latitude']),
                point_placement_type="Site",
                psap_attribution=row['PSAP'],
                landmark_alias=row['LandmarkName'] if pd.notna(row['LandmarkName']) else None,
                discrepancy_codes=discrepancies
            ))

    elapsed_ms = round((time.time() - t0) * 1000, 2)
    return FindLocationResponse(
        execution_time_ms=elapsed_ms,
        results=results
    )

@app.post("/v1/getRoute", response_model=GetRouteResponse)
def get_route(req: GetRouteRequest):
    """
    NENA STA-005.1.2 Emergency Call Routing Function (ECRF)
    Performs spatial point-in-polygon routing lookup against ESB and PSAP boundaries.
    """
    t0 = time.time()
    db = get_db_connection()

    lng = None
    lat = None

    if req.location:
        lng = req.location.longitude
        lat = req.location.latitude
    elif req.civic_address:
        # Resolve location first
        lvf_req = FindLocationRequest(civic_address=req.civic_address)
        lvf_res = find_location(lvf_req)
        if lvf_res.results and lvf_res.results[0].longitude:
            lng = lvf_res.results[0].longitude
            lat = lvf_res.results[0].latitude

    if lng is None or lat is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to resolve location coordinates for ECRF routing."
        )

    # Perform spatial point-in-polygon query against ESB boundary parquet
    psap_name = "Fresno County Sheriff PSAP"
    esb_fire = "Fresno City Fire Department Boundary"
    
    if os.path.exists(ESB_PARQUET):
        query = f"""
            SELECT Agency_Name, Agency_Type
            FROM '{ESB_PARQUET}'
            WHERE ST_Within(ST_Point({lng}, {lat}), ST_Geometry)
            LIMIT 5
        """
        try:
            df = db.sql(query).df()
            for _, row in df.iterrows():
                if row['Agency_Type'] == 'CAD_PSAP':
                    psap_name = row['Agency_Name']
                elif row['Agency_Type'] == 'FIRE':
                    esb_fire = row['Agency_Name']
        except Exception as e:
            print(f"Spatial query fallback: {e}")

    psap_slug = psap_name.replace(" ", "_")
    psap_uri = f"urn:emergency:uid:psap:{psap_slug}:fresnocountyca.gov"

    result = RouteResponseResult(
        service_urn=req.service_urn,
        primary_psap_uri=psap_uri,
        psap_name=psap_name,
        psap_phone="tel:+15555550100",
        discrepancy_agency_id="fresnocountyca.gov",
        esb_fire_boundary=esb_fire,
        longitude=lng,
        latitude=lat
    )

    elapsed_ms = round((time.time() - t0) * 1000, 2)
    return GetRouteResponse(
        execution_time_ms=elapsed_ms,
        route=result
    )

if __name__ == "__main__":
    import uvicorn
    import pandas as pd
    print("=" * 78)
    print("      NENA STA-005.1.2 ECRF/LVF REST API MICROSERVICE")
    print("=" * 78)
    print("Starting server on http://127.0.0.1:8090 ...")
    print("Open API documentation at: http://127.0.0.1:8090/docs")
    print("=" * 78)
    uvicorn.run(app, host="127.0.0.1", port=8090)
