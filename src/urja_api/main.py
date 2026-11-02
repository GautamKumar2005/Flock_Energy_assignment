"""
Main FastAPI application for the Urja Meter Ops API.

This service acts as a clean, documented API layer over the legacy Urja Meter Ops
portal. It handles authentication, data fetching, response shaping, caching,
geospatial queries, and analytical aggregation — so consumers never need to
touch the original portal.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from .dashboard import DASHBOARD_HTML
from .models import (
    DTSummary,
    EnergyReading,
    HierarchyLevel,
    MeterDetail,
    MeterGeo,
    MeterHierarchy,
    MeterNameplate,
    MeterSummary,
    NearbyResponse,
    NetworkStats,
    PagedDTs,
    PagedMeters,
    SyncStatus,
)
from .portal_client import UrjaPortalClient
from .store import LocalIndexStore

# --------------------------------------------------------------------------- #
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Single shared client and local store
_client: Optional[UrjaPortalClient] = None
_store = LocalIndexStore(ttl_seconds=600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client
    logger.info("Initializing Urja API service...")
    _client = UrjaPortalClient()
    try:
        await _client._login()
        logger.info("Portal session authenticated successfully")
        # Pre-warm local index cache from bulk export
        await _store.ensure_synced(_client)
    except Exception as exc:
        logger.warning("Portal initial sync deferred: %s", exc)
    yield
    if _client:
        await _client.close()
    logger.info("Urja API service shut down")


# --------------------------------------------------------------------------- #

app = FastAPI(
    title="Urja Meter Ops API",
    version="1.0.0",
    description=(
        "A clean, documented REST API over the Urja Meter Ops distribution "
        "metering portal. Exposes meter nameplates, time-series consumption readings, "
        "distribution transformers, reconstructed network hierarchy, geospatial radius search, "
        "and caching without requiring direct portal access."
    ),
    contact={"name": "Urja API Engineering", "url": "https://github.com/flock-energy/urja-api"},
    license_info={"name": "MIT"},
    lifespan=lifespan,
    openapi_tags=[
        {"name": "meters", "description": "Smart meter lookup, nameplate details, and queries"},
        {"name": "spatial", "description": "Geospatial radius queries (Haversine search)"},
        {"name": "consumption", "description": "Time-series energy readings (kWh, kVAh, Voltage)"},
        {"name": "transformers", "description": "Distribution transformer (DT) records"},
        {"name": "network", "description": "Reconstructed network hierarchy (Zone → Substation → Feeder → DT)"},
        {"name": "analytics", "description": "Aggregated fleet statistics and breakdowns"},
        {"name": "system", "description": "Health, cache freshness, and synchronization"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_client() -> UrjaPortalClient:
    global _client
    if _client is None:
        _client = UrjaPortalClient()
    return _client


# --------------------------------------------------------------------------- #
# Helper: shape portal responses into our clean models                         #
# --------------------------------------------------------------------------- #


def _shape_meter_summary(raw: dict) -> MeterSummary:
    return MeterSummary(
        meter_id=raw["meterId"],
        serial_no=raw.get("serialNo", ""),
        make=raw.get("make", ""),
        phase_type=raw.get("phaseType", ""),
        install_status=raw.get("installStatus", ""),
        dt_code=raw.get("dtCode", ""),
    )


def _shape_meter_detail(
    raw_detail: dict,
    geo_data: dict | None,
    meter_id: str,
) -> MeterDetail:
    """
    Converts the decoded SvelteKit __data.json into a MeterDetail.
    Flattens dynamic nameplate parameters and extracts hierarchy.
    """
    detail_block = raw_detail.get("detail", {})
    params = detail_block.get("data", [])
    np: dict[str, str] = {}
    for param in params:
        if isinstance(param, dict) and "parameterName" in param:
            np[param["parameterName"]] = str(param.get("parameterValue", ""))

    nameplate = MeterNameplate(
        meter_id=meter_id,
        serial_no=np.get("Serial No"),
        make=np.get("Make"),
        phase_type=np.get("Phase Type"),
        install_status=np.get("Installation Status"),
        install_type=np.get("Installation Type"),
    )

    hier_raw = raw_detail.get("hierarchy", {})

    def parse_hier(val: str | None) -> HierarchyLevel | None:
        if not val:
            return None
        if "(" in val and val.endswith(")"):
            name_part, code_part = val.rsplit("(", 1)
            return HierarchyLevel(name=name_part.strip(), code=code_part.rstrip(")").strip())
        return HierarchyLevel(name=val, code=val)

    hierarchy = MeterHierarchy(
        zone=parse_hier(hier_raw.get("Zone")),
        circle=parse_hier(hier_raw.get("Circle")),
        division=parse_hier(hier_raw.get("Division")),
        subdivision=parse_hier(hier_raw.get("Subdivision")),
        substation=parse_hier(hier_raw.get("Sub Station")),
        feeder=parse_hier(hier_raw.get("Feeder")),
        dt=parse_hier(hier_raw.get("DT")),
    )

    geo = None
    if geo_data:
        try:
            geo = MeterGeo(
                latitude=float(geo_data.get("latitude") or geo_data.get("lat")),
                longitude=float(geo_data.get("longitude") or geo_data.get("lng")),
            )
        except (KeyError, ValueError, TypeError):
            pass

    return MeterDetail(
        meter_id=meter_id,
        nameplate=nameplate,
        hierarchy=hierarchy,
        geo=geo,
    )


def _shape_dt(raw: dict) -> DTSummary:
    return DTSummary(
        code=raw["code"],
        name=raw["name"],
        feeder_code=raw.get("feederCode", ""),
        capacity_kva=int(raw.get("capacityKva", 0)),
    )


# --------------------------------------------------------------------------- #
# Modern Web Client (HTML Dashboard)                                          #
# --------------------------------------------------------------------------- #


@app.get(
    "/",
    response_class=HTMLResponse,
    include_in_schema=False,
    summary="Modern Web Client Dashboard",
)
async def root_dashboard():
    """Serves the modern dark-mode web application for meter exploration and analytics."""
    return HTMLResponse(content=DASHBOARD_HTML, status_code=200)


@app.get(
    "/dashboard",
    response_class=HTMLResponse,
    include_in_schema=False,
    summary="Modern Web Client Dashboard",
)
async def dashboard_alias():
    return HTMLResponse(content=DASHBOARD_HTML, status_code=200)


@app.get(
    "/api",
    tags=["system"],
    summary="API Service Index",
    description="Index of available API resources and documentation links.",
)
async def api_index() -> dict[str, str]:
    return {
        "service": "Urja Meter Ops API",
        "version": "1.0.0",
        "dashboard": "/",
        "docs_swagger": "/docs",
        "docs_redoc": "/redoc",
        "openapi_spec": "/openapi.json",
        "health": "/health",
        "meters": "/meters",
        "nearby_search": "/meters/nearby",
        "query_studio": "/meters/query",
        "analytics_stats": "/meters/stats",
        "transformers": "/transformers",
        "network_hierarchy": "/network",
        "cache_sync_status": "/sync/status",
    }


# --------------------------------------------------------------------------- #
# Meters                                                                      #
# --------------------------------------------------------------------------- #


@app.get(
    "/meters",
    response_model=PagedMeters,
    tags=["meters"],
    summary="List / search meters",
    description=(
        "Returns a paginated list of meters. Pass `q` to search by meter ID "
        "or serial number prefix. 20 results per page."
    ),
)
async def list_meters(
    q: str = Query("", description="Search term (meter ID or serial number prefix)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
) -> PagedMeters:
    c = get_client()
    try:
        raw = await c.search_meters(q=q, page=page)
        return PagedMeters(
            total=raw["total"],
            page=page,
            page_size=20,
            data=[_shape_meter_summary(m) for m in raw.get("data", [])],
        )
    except Exception as exc:
        logger.warning("Portal search failed, falling back to local index: %s", exc)
        await _store.ensure_synced(c)
        return _store.search(q=q, page=page, page_size=20)


@app.get(
    "/meters/query",
    response_model=PagedMeters,
    tags=["meters"],
    summary="Advanced multi-attribute meter search",
    description=(
        "Answers questions the legacy portal cannot answer: filter meters across "
        "manufacturer (make), phase type (single/three), installation status, "
        "distribution transformer (dt_code), feeder, or zone."
    ),
)
async def query_meters(
    q: str = Query("", description="Search substring in meter ID or serial number"),
    make: Optional[str] = Query(None, description="Filter by make (e.g. HPL, Genus, L&T)"),
    phase_type: Optional[str] = Query(None, description="Filter by phase (single or three)"),
    install_status: Optional[str] = Query(None, description="Filter by status (Commissioned, Decommissioned, Pending)"),
    dt_code: Optional[str] = Query(None, description="Filter by DT code (e.g. DT-001)"),
    feeder_code: Optional[str] = Query(None, description="Filter by feeder code (e.g. F-001)"),
    zone_code: Optional[str] = Query(None, description="Filter by zone code (e.g. Z-01)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=500, description="Items per page"),
) -> PagedMeters:
    await _store.ensure_synced(get_client())
    return _store.search(
        q=q,
        make=make,
        phase_type=phase_type,
        install_status=install_status,
        dt_code=dt_code,
        feeder_code=feeder_code,
        zone_code=zone_code,
        page=page,
        page_size=page_size,
    )


@app.get(
    "/meters/nearby",
    response_model=NearbyResponse,
    tags=["spatial"],
    summary="Find meters near GPS coordinates",
    description=(
        "Computes great-circle distances using the Haversine formula and returns "
        "all meters within radius_km of the given latitude/longitude, sorted nearest first."
    ),
)
async def get_meters_nearby(
    lat: float = Query(..., description="Target latitude (e.g. 26.9124)"),
    lon: float = Query(..., description="Target longitude (e.g. 75.7873)"),
    radius_km: float = Query(5.0, gt=0, le=50.0, description="Radius in kilometers (default 5km)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
) -> NearbyResponse:
    await _store.ensure_synced(get_client())
    return _store.find_nearby(center_lat=lat, center_lon=lon, radius_km=radius_km, limit=limit)


@app.get(
    "/meters/stats",
    response_model=NetworkStats,
    tags=["analytics"],
    summary="Fleet analytics and network breakdown",
    description=(
        "Returns aggregated metrics across the entire distribution network: "
        "active vs decommissioned ratio, single vs three phase distribution, "
        "breakdown by manufacturer make, and distribution transformers."
    ),
)
async def get_network_stats() -> NetworkStats:
    await _store.ensure_synced(get_client())
    return _store.get_stats()


@app.get(
    "/meters/{meter_id}",
    response_model=MeterDetail,
    tags=["meters"],
    summary="Get full meter detail",
    description=(
        "Returns nameplate parameters, network hierarchy (Zone → Feeder → DT), and GPS "
        "coordinates for the specified meter."
    ),
)
async def get_meter(meter_id: str) -> MeterDetail:
    c = get_client()
    try:
        raw_detail = await c.get_meter_detail(meter_id)
        if not raw_detail or not raw_detail.get("meterId"):
            raise ValueError(f"Meter {meter_id} not found in portal")
    except HTTPException:
        raise
    except Exception as exc:
        # Check local store before 404
        if meter_id in _store._meters_by_id:
            m = _store._meters_by_id[meter_id]
            geo = m.get("geo") or {}
            return MeterDetail(
                meter_id=meter_id,
                nameplate=MeterNameplate(
                    meter_id=meter_id,
                    serial_no=m.get("serialNo"),
                    make=m.get("make"),
                    phase_type=m.get("phaseType"),
                    install_status=m.get("installStatus"),
                    install_type=m.get("installType"),
                ),
                hierarchy=MeterHierarchy(
                    zone=HierarchyLevel(name=m.get("hierarchy", {}).get("zone", {}).get("name", ""), code=m.get("hierarchy", {}).get("zone", {}).get("code", "")),
                    circle=HierarchyLevel(name=m.get("hierarchy", {}).get("circle", {}).get("name", ""), code=m.get("hierarchy", {}).get("circle", {}).get("code", "")),
                    division=HierarchyLevel(name=m.get("hierarchy", {}).get("division", {}).get("name", ""), code=m.get("hierarchy", {}).get("division", {}).get("code", "")),
                    subdivision=HierarchyLevel(name=m.get("hierarchy", {}).get("subdivision", {}).get("name", ""), code=m.get("hierarchy", {}).get("subdivision", {}).get("code", "")),
                    substation=HierarchyLevel(name=m.get("hierarchy", {}).get("substation", {}).get("name", ""), code=m.get("hierarchy", {}).get("substation", {}).get("code", "")),
                    feeder=HierarchyLevel(name=m.get("hierarchy", {}).get("feeder", {}).get("name", ""), code=m.get("hierarchy", {}).get("feeder", {}).get("code", "")),
                    dt=HierarchyLevel(name=m.get("hierarchy", {}).get("dt", {}).get("name", ""), code=m.get("hierarchy", {}).get("dt", {}).get("code", "")),
                ),
                geo=MeterGeo(latitude=float(geo.get("lat", 0)), longitude=float(geo.get("lng", 0))) if geo else None,
            )
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Meter {meter_id!r} not found: {exc}") from exc

    geo_data = None
    try:
        geo_data = await c.get_meter_geo(meter_id)
    except Exception:
        pass

    return _shape_meter_detail(raw_detail, geo_data, meter_id)


# --------------------------------------------------------------------------- #
# Consumption                                                                 #
# --------------------------------------------------------------------------- #


@app.get(
    "/meters/{meter_id}/energy",
    response_model=list[EnergyReading],
    tags=["consumption"],
    summary="Meter consumption readings",
    description=(
        "Returns all available time-series energy readings for the meter. "
        "Each record contains timestamp, cumulative active energy (kWh), apparent energy (kVAh), "
        "and R-phase voltage."
    ),
)
async def get_meter_energy(meter_id: str) -> list[EnergyReading]:
    c = get_client()
    try:
        readings = await c.get_meter_energy(meter_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No readings for meter {meter_id!r}: {exc}") from exc

    return [
        EnergyReading(
            timestamp=r["timestamp"],
            kwh=r.get("kwh"),
            kvah=r.get("kvah"),
            volt_r=r.get("voltR"),
        )
        for r in readings
    ]


# --------------------------------------------------------------------------- #
# Distribution Transformers                                                   #
# --------------------------------------------------------------------------- #


@app.get(
    "/transformers",
    response_model=PagedDTs,
    tags=["transformers"],
    summary="List distribution transformers",
    description="Returns a paginated list of distribution transformers (DTs). 20 per page.",
)
async def list_dts(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
) -> PagedDTs:
    c = get_client()
    raw = await c.list_dts(page=page)
    return PagedDTs(
        total=raw["total"],
        page=page,
        page_size=20,
        data=[_shape_dt(d) for d in raw.get("data", [])],
    )


# --------------------------------------------------------------------------- #
# Network hierarchy                                                           #
# --------------------------------------------------------------------------- #


@app.get(
    "/network",
    tags=["network"],
    summary="Reconstructed network hierarchy",
    description=(
        "Reconstructs the complete distribution network topology from meter records: "
        "Zone → Circle → Division → Subdivision → Substation → Feeder → DT → Meters. "
        "Served with low-latency caching."
    ),
)
async def get_network() -> Any:
    await _store.ensure_synced(get_client())
    return _store.get_network_hierarchy()


# --------------------------------------------------------------------------- #
# System & Cache Management                                                    #
# --------------------------------------------------------------------------- #


@app.post(
    "/sync",
    response_model=SyncStatus,
    tags=["system"],
    summary="Force refresh local cache from portal",
    description="Triggers a fresh bulk export from the Urja portal and updates the local query index.",
)
async def force_sync() -> SyncStatus:
    await _store.ensure_synced(get_client(), force=True)
    return _store.get_sync_status()


@app.get(
    "/sync/status",
    response_model=SyncStatus,
    tags=["system"],
    summary="Check cache freshness and sync status",
)
async def get_sync_status() -> SyncStatus:
    return _store.get_sync_status()


@app.get(
    "/health",
    tags=["system"],
    summary="Service health check",
)
async def health() -> dict[str, Any]:
    sync_status = _store.get_sync_status()
    return {
        "status": "ok",
        "service": "urja-api",
        "version": "1.0.0",
        "portal_connected": _client is not None,
        "indexed_meters": sync_status.total_meters,
    }
