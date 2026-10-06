#!/usr/bin/env python3
"""
scripts/ng911_schemas.py

Production-grade Pydantic v2 data models for the NG911 Cloud-Native Pipeline.

Models:
1. `NENAAddressPoint`: NENA-STA-010.3 Site/Structure Address Point (SSAP) schema
2. `NENARoadCenterline`: NENA-STA-010.3 Road Centerline (RCL) schema
3. `NENAQACollisionScorecard`: Cal OES 98% NG911 Transition Readiness Scorecard
4. `GeoLibreProjectConfig`: GeoLibre Project & PMTiles Layer spec validator
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict

class NENAAddressPoint(BaseModel):
    """NENA-STA-010.3 Site/Structure Address Point (SSAP) Data Model."""
    model_config = ConfigDict(extra="ignore")

    SSAP_NGUID: str = Field(..., description="Globally unique NENA NGUID URN")
    DisclID: str = Field("fresnocountyca.gov", description="Discrepancy agency domain identifier")
    HNO: str = Field(..., description="House Number (civic address number)")
    PRD: Optional[str] = Field(None, description="Pre-Directional (N, S, E, W)")
    STN: str = Field(..., description="Street Name")
    STS: Optional[str] = Field(None, description="Street Type (ST, AVE, BLVD)")
    POD: Optional[str] = Field(None, description="Post-Directional")
    Unit: Optional[str] = Field(None, description="Sub-address unit or apartment number")
    Muni: Optional[str] = Field("FRESNO", description="Incorporated Municipality")
    CommunityName: str = Field("FRESNO", description="Unincorporated community or postal city")
    County: str = Field("FRESNO", description="County name")
    State: str = Field("CA", description="Two-letter state abbreviation")
    Country: str = Field("US", description="Two-letter country code")
    PostCode: Optional[str] = Field(None, description="5-digit Postal Code")
    PSAP: Optional[str] = Field(None, description="CAD/PSAP Emergency Dispatch Agency")
    ESB_Fire: Optional[str] = Field(None, description="Fire Protection District Boundary")
    LandmarkName: Optional[str] = Field(None, description="Authoritative POI or landmark alias")
    ConflationStatus: Literal["CONFLATED", "COUNTY_ONLY", "OVERTURE_ONLY"] = Field(
        "COUNTY_ONLY", description="Ingestion & conflation origin"
    )
    Longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 Longitude")
    Latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 Latitude")
    SpatialOffsetMeters: Optional[float] = Field(None, ge=0.0, description="Spatial offset from Overture reference")

    @field_validator("Country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        if v.upper() != "US":
            raise ValueError("Country must be 'US'")
        return v.upper()

class NENARoadCenterline(BaseModel):
    """NENA-STA-010.3 Road Centerline (RCL) Data Model."""
    model_config = ConfigDict(extra="ignore")

    RCL_NGUID: str = Field(..., description="Globally unique NENA RCL NGUID URN")
    DisclID: str = Field("fresnocountyca.gov", description="Discrepancy agency domain identifier")
    FullStreetName: str = Field(..., description="Full concatenated street name")
    FromAddr_L: Optional[int] = Field(None, ge=0, description="Left side starting address number")
    ToAddr_L: Optional[int] = Field(None, ge=0, description="Left side ending address number")
    FromAddr_R: Optional[int] = Field(None, ge=0, description="Right side starting address number")
    ToAddr_R: Optional[int] = Field(None, ge=0, description="Right side ending address number")
    Parity_L: Optional[Literal["O", "E", "B", "Z"]] = Field(None, description="Left side address parity (Odd/Even/Both/Zero)")
    Parity_R: Optional[Literal["O", "E", "B", "Z"]] = Field(None, description="Right side address parity")
    SpeedLimit: Optional[int] = Field(None, ge=5, le=85, description="Posted speed limit (MPH)")
    RoadClass: Optional[str] = Field(None, description="Functional road classification")

class NENAQACollisionScorecard(BaseModel):
    """Cal OES 98% NG911 Transition Readiness Scorecard."""
    model_config = ConfigDict(extra="ignore")

    total_ssap: int = Field(..., ge=0, description="Total Site/Structure Address Points")
    total_rcl: int = Field(..., ge=0, description="Total Road Centerline segments")
    snapped_within_50m: int = Field(..., ge=0, description="Address points snapped to RCL within 50m")
    excessive_offset_count: int = Field(..., ge=0, description="Address points with >50m offset")
    snapped_percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of SSAP snapped within 50m")
    psap_coverage_percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of SSAP with valid PSAP boundary")
    readiness_status: Literal["PASS_98_PERCENT_READY", "ACTION_REQUIRED_DEFICIENT"] = Field(
        ..., description="Cal OES 98% readiness evaluation result"
    )

class GeoLibreLayerConfig(BaseModel):
    """GeoLibre Layer spec validator."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Layer unique ID")
    name: str = Field(..., description="Display layer name")
    type: Literal["geojson", "pmtiles", "vector-tiles", "raster"] = Field(..., description="Layer renderer type")
    visible: bool = Field(True, description="Default visibility")
    opacity: float = Field(1.0, ge=0.0, le=1.0, description="Layer opacity")
    source: Dict[str, Any] = Field(..., description="Layer source parameters")
    sourcePath: str = Field(..., description="Source URL or file path")
    style: Dict[str, Any] = Field(default_factory=dict, description="Style configuration")
    popup: Optional[Dict[str, Any]] = Field(None, description="Popup field configuration")

class GeoLibreProjectConfig(BaseModel):
    """GeoLibre Project File (.geolibre.json) spec validator."""
    model_config = ConfigDict(extra="ignore")

    version: str = Field("0.1.0", description="GeoLibre project schema version")
    name: str = Field(..., description="Project title")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Project metadata")
    mapView: Dict[str, Any] = Field(..., description="Default map center, zoom, and bbox")
    basemapStyleUrl: str = Field(..., description="Vector basemap tile style URL")
    basemapVisible: bool = Field(True)
    basemapOpacity: float = Field(1.0, ge=0.0, le=1.0)
    primaryRenderer: str = Field("maplibre")
    layers: List[GeoLibreLayerConfig] = Field(..., min_length=1, description="Map layer array")

def validate_pipeline_schemas():
    """Runs verification tests for custom Pydantic v2 schemas."""
    print("=" * 70)
    print("   NG911 PIPELINE PYDANTIC V2 SCHEMA VALIDATION")
    print("=" * 70)

    # 1. Test Address Point Schema
    addr = NENAAddressPoint(
        SSAP_NGUID="urn:nena:ssap:fresnocountyca.gov:1001",
        HNO="2600",
        STN="FRESNO ST",
        Longitude=-119.7871,
        Latitude=36.7468,
        PSAP="Fresno Police CAD",
        ESB_Fire="Fresno City Fire District",
        ConflationStatus="CONFLATED"
    )
    print(f"[PASS] NENAAddressPoint validated: {addr.SSAP_NGUID} -> {addr.HNO} {addr.STN}")

    # 2. Test Road Centerline Schema
    rcl = NENARoadCenterline(
        RCL_NGUID="urn:nena:rcl:fresnocountyca.gov:5001",
        FullStreetName="E VENTURA AVE",
        FromAddr_L=100,
        ToAddr_L=199,
        FromAddr_R=100,
        ToAddr_R=198,
        Parity_L="O",
        Parity_R="E",
        SpeedLimit=35,
        RoadClass="arterial"
    )
    print(f"[PASS] NENARoadCenterline validated: {rcl.RCL_NGUID} -> {rcl.FullStreetName} ({rcl.Parity_L}/{rcl.Parity_R})")

    # 3. Test Scorecard Schema
    scorecard = NENAQACollisionScorecard(
        total_ssap=466754,
        total_rcl=53474,
        snapped_within_50m=274247,
        excessive_offset_count=91072,
        snapped_percentage=75.07,
        psap_coverage_percentage=84.85,
        readiness_status="ACTION_REQUIRED_DEFICIENT"
    )
    print(f"[PASS] NENAQACollisionScorecard validated: Snapped={scorecard.snapped_percentage}% ({scorecard.readiness_status})")

    print("-" * 70)
    print("All NG911 custom Pydantic v2 models validated successfully!\n")

if __name__ == "__main__":
    validate_pipeline_schemas()
