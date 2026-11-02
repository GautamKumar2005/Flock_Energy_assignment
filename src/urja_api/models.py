"""
Pydantic models for the Urja API — the clean, public-facing data shapes.
These decouple our API contract from the portal's internal representation.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ------------------------------------------------------------------ #
# Meters                                                               #
# ------------------------------------------------------------------ #


class MeterSummary(BaseModel):
    """Lightweight meter record returned in list/search results."""

    meter_id: str = Field(..., description="Unique meter identifier (e.g. J100000)")
    serial_no: str = Field(..., description="Physical serial number stamped on the meter")
    make: str = Field(..., description="Manufacturer (e.g. HPL, L&T, Genus)")
    phase_type: str = Field(..., description="'single' or 'three'")
    install_status: str = Field(
        ..., description="Installation status (e.g. Installed, Faulty, Decommissioned)"
    )
    dt_code: str = Field(..., description="Distribution transformer code this meter belongs to")
    latitude: Optional[float] = Field(None, description="Latitude coordinate")
    longitude: Optional[float] = Field(None, description="Longitude coordinate")


class HierarchyLevel(BaseModel):
    name: str
    code: str


class MeterHierarchy(BaseModel):
    zone: Optional[HierarchyLevel] = None
    circle: Optional[HierarchyLevel] = None
    division: Optional[HierarchyLevel] = None
    subdivision: Optional[HierarchyLevel] = None
    substation: Optional[HierarchyLevel] = None
    feeder: Optional[HierarchyLevel] = None
    dt: Optional[HierarchyLevel] = None


class MeterGeo(BaseModel):
    latitude: float
    longitude: float


class MeterNameplate(BaseModel):
    """Key nameplate parameters (dynamic list from portal, we flatten common ones)."""

    meter_id: str
    serial_no: Optional[str] = None
    make: Optional[str] = None
    phase_type: Optional[str] = None
    install_status: Optional[str] = None
    install_type: Optional[str] = None


class MeterDetail(BaseModel):
    """Full meter record including nameplate, hierarchy, and geo."""

    meter_id: str
    nameplate: MeterNameplate
    hierarchy: MeterHierarchy
    geo: Optional[MeterGeo] = None


# ------------------------------------------------------------------ #
# Consumption / Energy                                                 #
# ------------------------------------------------------------------ #


class EnergyReading(BaseModel):
    """A single metered consumption snapshot."""

    timestamp: str = Field(..., description="Reading timestamp (portal format: DD/MM/YYYY HH:MM)")
    kwh: Optional[str] = Field(None, description="Cumulative active energy (kWh)")
    kvah: Optional[str] = Field(None, description="Cumulative apparent energy (kVAh)")
    volt_r: Optional[str] = Field(None, description="R-phase voltage (V)")


# ------------------------------------------------------------------ #
# Distribution Transformers                                            #
# ------------------------------------------------------------------ #


class DTSummary(BaseModel):
    """Distribution transformer record."""

    code: str = Field(..., description="DT code (e.g. DT-001)")
    name: str = Field(..., description="Human-readable DT name")
    feeder_code: str = Field(..., description="Parent feeder code")
    capacity_kva: int = Field(..., description="Rated capacity in kVA")


# ------------------------------------------------------------------ #
# Network hierarchy                                                    #
# ------------------------------------------------------------------ #


class DTNode(BaseModel):
    code: str
    name: str
    capacity_kva: int
    meter_count: int


class FeederNode(BaseModel):
    code: str
    name: str
    dts: list[DTNode]


class SubstationNode(BaseModel):
    code: str
    name: str
    feeders: list[FeederNode]


class NetworkHierarchy(BaseModel):
    """
    Reconstructed network topology derived from meter export data.
    Zone → Circle → Division → Subdivision → Substation → Feeder → DT → Meters
    """

    zone_code: str
    zone_name: str
    substations: list[SubstationNode]


# ------------------------------------------------------------------ #
# Paged responses                                                      #
# ------------------------------------------------------------------ #


class PagedMeters(BaseModel):
    total: int
    page: int
    page_size: int
    data: list[MeterSummary]


class PagedDTs(BaseModel):
    total: int
    page: int
    page_size: int
    data: list[DTSummary]


# ------------------------------------------------------------------ #
# Local Index & Analytics Models                                     #
# ------------------------------------------------------------------ #


class NearbyMeter(BaseModel):
    meter_id: str
    serial_no: str
    make: str
    phase_type: str
    install_status: str
    dt_code: str
    latitude: float
    longitude: float
    distance_km: float


class NearbyResponse(BaseModel):
    center_latitude: float
    center_longitude: float
    radius_km: float
    count: int
    meters: list[NearbyMeter]


class NetworkStats(BaseModel):
    total_meters: int
    total_dts: int
    active_meters: int
    faulty_meters: int = 0
    decommissioned_meters: int
    pending_meters: int = 0
    single_phase_meters: int
    three_phase_meters: int
    makes_breakdown: dict[str, int]
    statuses_breakdown: dict[str, int]
    phases_breakdown: dict[str, int]
    dts_breakdown: dict[str, int]


class SyncStatus(BaseModel):
    status: str
    total_meters: int
    last_synced_at: Optional[str] = None
    ttl_seconds: int
