"""
In-memory query layer, geospatial index, and caching store.

Reconstructs and indexes the full meter dataset retrieved via the portal's bulk HMAC export endpoint.
Provides capabilities the portal cannot provide:
1. Spatial radius queries (Haversine distance search)
2. Multi-attribute filtering (make, phase, status, DT, feeder, zone)
3. Instant aggregate analytics and breakdown summaries
4. Network hierarchy caching for sub-millisecond response times
5. Configurable TTL and graceful fallback on portal degradation
"""
from __future__ import annotations

import math
import time
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .models import (
    NearbyMeter,
    NearbyResponse,
    NetworkStats,
    SyncStatus,
    MeterSummary,
    PagedMeters,
)
from .portal_client import UrjaPortalClient

logger = logging.getLogger(__name__)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in km."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 3)


class LocalIndexStore:
    def __init__(self, ttl_seconds: int = 600) -> None:
        self.ttl_seconds = ttl_seconds
        self.last_synced_at: Optional[float] = None
        self.meters: list[dict[str, Any]] = []
        self._meters_by_id: dict[str, dict[str, Any]] = {}
        self._hierarchy_cache: Optional[dict[str, Any]] = None

    @property
    def is_stale(self) -> bool:
        if self.last_synced_at is None or not self.meters:
            return True
        return (time.time() - self.last_synced_at) > self.ttl_seconds

    async def ensure_synced(self, client: UrjaPortalClient, force: bool = False) -> None:
        if not force and not self.is_stale:
            return

        try:
            logger.info("Syncing local meter index via bulk export...")
            raw_meters = await client.export_meters()
            if raw_meters:
                self.meters = raw_meters
                self._meters_by_id = {m.get("meterId", ""): m for m in raw_meters if m.get("meterId")}
                self._hierarchy_cache = None  # Invalidate cached tree
                self.last_synced_at = time.time()
                logger.info("Successfully synced %d meters into local index", len(self.meters))
        except Exception as exc:
            logger.error("Failed to sync meter index: %s", exc)
            # If we already have cached data, keep serving it (graceful degradation)
            if not self.meters:
                raise

    def get_sync_status(self) -> SyncStatus:
        last_str = None
        if self.last_synced_at:
            last_str = datetime.fromtimestamp(self.last_synced_at, tz=timezone.utc).isoformat()
        return SyncStatus(
            status="healthy" if self.meters else "uninitialized",
            total_meters=len(self.meters),
            last_synced_at=last_str,
            ttl_seconds=self.ttl_seconds,
        )

    def find_nearby(
        self,
        center_lat: float,
        center_lon: float,
        radius_km: float = 5.0,
        limit: int = 50,
    ) -> NearbyResponse:
        """Find meters within radius_km of (center_lat, center_lon) sorted by distance."""
        results: list[NearbyMeter] = []

        for m in self.meters:
            geo = m.get("geo") or {}
            lat = geo.get("lat") or geo.get("latitude")
            lng = geo.get("lng") or geo.get("longitude")
            if lat is None or lng is None:
                continue

            try:
                m_lat = float(lat)
                m_lng = float(lng)
            except (ValueError, TypeError):
                continue

            dist = haversine_km(center_lat, center_lon, m_lat, m_lng)
            if dist <= radius_km:
                results.append(
                    NearbyMeter(
                        meter_id=m.get("meterId", ""),
                        serial_no=m.get("serialNo", ""),
                        make=m.get("make", ""),
                        phase_type=m.get("phaseType", ""),
                        install_status=m.get("installStatus", ""),
                        dt_code=m.get("dtCode", ""),
                        latitude=m_lat,
                        longitude=m_lng,
                        distance_km=dist,
                    )
                )

        results.sort(key=lambda x: x.distance_km)
        total_found = len(results)
        return NearbyResponse(
            center_latitude=center_lat,
            center_longitude=center_lon,
            radius_km=radius_km,
            count=total_found,
            meters=results[:limit],
        )

    def search(
        self,
        q: str = "",
        make: Optional[str] = None,
        phase_type: Optional[str] = None,
        install_status: Optional[str] = None,
        dt_code: Optional[str] = None,
        feeder_code: Optional[str] = None,
        zone_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PagedMeters:
        """Multi-attribute filtering over local index."""
        filtered = self.meters

        if q:
            q_lower = q.lower().strip()
            filtered = [
                m for m in filtered
                if q_lower in m.get("meterId", "").lower() or q_lower in m.get("serialNo", "").lower()
            ]

        if make:
            make_lower = make.lower().strip()
            filtered = [m for m in filtered if m.get("make", "").lower() == make_lower]

        if phase_type:
            p_lower = phase_type.lower().strip()
            filtered = [m for m in filtered if m.get("phaseType", "").lower() == p_lower]

        if install_status:
            s_lower = install_status.lower().strip()
            filtered = [m for m in filtered if m.get("installStatus", "").lower() == s_lower]

        if dt_code:
            dt_lower = dt_code.lower().strip()
            filtered = [m for m in filtered if m.get("dtCode", "").lower() == dt_lower]

        if feeder_code:
            f_lower = feeder_code.lower().strip()
            filtered = [
                m for m in filtered
                if m.get("hierarchy", {}).get("feeder", {}).get("code", "").lower() == f_lower
            ]

        if zone_code:
            z_lower = zone_code.lower().strip()
            filtered = [
                m for m in filtered
                if m.get("hierarchy", {}).get("zone", {}).get("code", "").lower() == z_lower
            ]

        total = len(filtered)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = filtered[start:end]

        def _extract_geo(item: dict) -> tuple[Optional[float], Optional[float]]:
            geo = item.get("geo") or {}
            lat = geo.get("lat") or geo.get("latitude")
            lng = geo.get("lng") or geo.get("longitude")
            try:
                m_lat = float(lat) if lat is not None else None
                m_lng = float(lng) if lng is not None else None
                return m_lat, m_lng
            except (ValueError, TypeError):
                return None, None

        data_items = []
        for m in page_items:
            lat, lng = _extract_geo(m)
            data_items.append(
                MeterSummary(
                    meter_id=m["meterId"],
                    serial_no=m.get("serialNo", ""),
                    make=m.get("make", ""),
                    phase_type=m.get("phaseType", ""),
                    install_status=m.get("installStatus", ""),
                    dt_code=m.get("dtCode", ""),
                    latitude=lat,
                    longitude=lng,
                )
            )

        return PagedMeters(
            total=total,
            page=page,
            page_size=page_size,
            data=data_items,
        )

    def get_stats(self) -> NetworkStats:
        """Generate network summary statistics."""
        makes: dict[str, int] = {}
        statuses: dict[str, int] = {}
        phases: dict[str, int] = {}
        dts: dict[str, int] = {}

        for m in self.meters:
            make = m.get("make") or "Unknown"
            makes[make] = makes.get(make, 0) + 1

            status = m.get("installStatus") or "Unknown"
            statuses[status] = statuses.get(status, 0) + 1

            phase = m.get("phaseType") or "Unknown"
            phases[phase] = phases.get(phase, 0) + 1

            dt = m.get("dtCode") or "Unknown"
            dts[dt] = dts.get(dt, 0) + 1

        return NetworkStats(
            total_meters=len(self.meters),
            total_dts=len(dts),
            active_meters=statuses.get("Installed", 0) + statuses.get("Active", 0),
            faulty_meters=statuses.get("Faulty", 0),
            decommissioned_meters=statuses.get("Decommissioned", 0),
            pending_meters=statuses.get("Pending", 0),
            single_phase_meters=phases.get("single", 0),
            three_phase_meters=phases.get("three", 0),
            makes_breakdown=makes,
            statuses_breakdown=statuses,
            phases_breakdown=phases,
            dts_breakdown=dts,
        )

    def get_network_hierarchy(self) -> dict[str, Any]:
        """Builds cached network topology."""
        if self._hierarchy_cache:
            return self._hierarchy_cache

        tree: dict[str, Any] = {}
        for m in self.meters:
            h = m.get("hierarchy", {})
            zone = h.get("zone", {})
            circle = h.get("circle", {})
            division = h.get("division", {})
            subdivision = h.get("subdivision", {})
            substation = h.get("substation", {})
            feeder = h.get("feeder", {})
            dt = h.get("dt", {})

            z_key = zone.get("code") or "Z-UNKNOWN"
            if z_key not in tree:
                tree[z_key] = {"code": z_key, "name": zone.get("name", "Zone"), "circles": {}}

            c_key = circle.get("code") or "C-UNKNOWN"
            circles = tree[z_key]["circles"]
            if c_key not in circles:
                circles[c_key] = {"code": c_key, "name": circle.get("name", "Circle"), "divisions": {}}

            d_key = division.get("code") or "D-UNKNOWN"
            divs = circles[c_key]["divisions"]
            if d_key not in divs:
                divs[d_key] = {"code": d_key, "name": division.get("name", "Division"), "subdivisions": {}}

            sd_key = subdivision.get("code") or "SD-UNKNOWN"
            sds = divs[d_key]["subdivisions"]
            if sd_key not in sds:
                sds[sd_key] = {"code": sd_key, "name": subdivision.get("name", "Subdivision"), "substations": {}}

            ss_key = substation.get("code") or "SS-UNKNOWN"
            sss = sds[sd_key]["substations"]
            if ss_key not in sss:
                sss[ss_key] = {"code": ss_key, "name": substation.get("name", "Substation"), "feeders": {}}

            f_key = feeder.get("code") or "F-UNKNOWN"
            feeders = sss[ss_key]["feeders"]
            if f_key not in feeders:
                feeders[f_key] = {"code": f_key, "name": feeder.get("name", "Feeder"), "dts": {}}

            dt_key = dt.get("code") or "DT-UNKNOWN"
            dts = feeders[f_key]["dts"]
            if dt_key not in dts:
                dts[dt_key] = {
                    "code": dt_key,
                    "name": dt.get("name", "Transformer"),
                    "meter_count": 0,
                    "meter_ids": [],
                }
            dts[dt_key]["meter_count"] += 1
            dts[dt_key]["meter_ids"].append(m.get("meterId"))

        keys_chain = ["circles", "divisions", "subdivisions", "substations", "feeders", "dts"]

        def flatten(node: dict, level: int = 0) -> dict:
            key = keys_chain[level] if level < len(keys_chain) else None
            if key is None:
                return {k: v for k, v in node.items() if k != "dts"}
            children = node.get(key, {})
            result = {k: v for k, v in node.items() if k != key}
            result[key] = [flatten(c, level + 1) for c in children.values()]
            return result

        zones = [flatten(z) for z in tree.values()]
        payload = {"zones": zones, "total_meters": len(self.meters)}
        self._hierarchy_cache = payload
        return payload
