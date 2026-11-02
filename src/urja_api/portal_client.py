"""
Urja Meter Ops API - Portal client
Handles session management and HMAC-signed requests to the portal backend
"""
from __future__ import annotations

import hashlib
import hmac
import time
import logging
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

PORTAL_BASE = "https://urja-ops.flockenergy.tech"
PORTAL_EMAIL = "operator@urja.local"
PORTAL_PASSWORD = "urja-ops-2026"


def _sign(method: str, path: str, query: str, secret: str) -> tuple[str, str]:
    """
    Compute HMAC-SHA256 signature required by /portal/export.

    Message format (newline-separated): METHOD\nPATH\nQUERY\nTIMESTAMP
    Returns (timestamp, hex_signature).
    """
    timestamp = str(int(time.time()))
    message = "\n".join([method.upper(), path, query, timestamp])
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return timestamp, sig


class UrjaPortalClient:
    """
    Thin async client wrapping the Urja Meter Ops portal's undocumented
    internal APIs discovered via JS bundle analysis.

    Auth: SvelteKit form action → better-auth session cookie
    Data: /portal/* REST endpoints (session-authenticated)
          /portal/export requires HMAC signing (key from /portal/keys)

    This client maintains a single httpx.AsyncClient with the session cookie,
    re-authenticating automatically on 401/403 responses.
    """

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._signing_secret: Optional[str] = None

    async def _make_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=PORTAL_BASE,
            headers={
                "User-Agent": "UrjaAPI/1.0 (+https://github.com/urja-api)",
                "Origin": PORTAL_BASE,
            },
            follow_redirects=False,
            timeout=30.0,
        )

    async def _login(self) -> None:
        """Authenticate and populate session cookie."""
        if self._client is None:
            self._client = await self._make_client()

        # GET /login first to prime any pre-session cookie (belt+suspenders)
        await self._client.get("/login")

        resp = await self._client.post(
            "/login",
            data={"email": PORTAL_EMAIL, "password": PORTAL_PASSWORD},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": f"{PORTAL_BASE}/login",
            },
        )
        # SvelteKit returns 200+JSON redirect or 303 on success
        if resp.status_code not in (200, 303):
            raise RuntimeError(
                f"Portal login failed: HTTP {resp.status_code}: {resp.text[:200]}"
            )
        logger.info("Portal session established")
        # Reset cached signing secret after re-login
        self._signing_secret = None

    async def _get_signing_secret(self) -> str:
        if self._signing_secret:
            return self._signing_secret
        data = await self._get("/portal/keys")
        self._signing_secret = data["data"]["signingSecret"]
        return self._signing_secret

    async def _get(self, path: str, params: dict | None = None, *, signed: bool = False) -> Any:
        """GET a portal endpoint, re-authenticating once on 401/403."""
        if self._client is None:
            await self._login()

        for attempt in range(2):
            extra_headers: dict[str, str] = {}

            if signed:
                secret = await self._get_signing_secret()
                query = urlencode(params or {})
                ts, sig = _sign("GET", path, query, secret)
                extra_headers = {"x-timestamp": ts, "x-signature": sig}

            resp = await self._client.get(  # type: ignore[union-attr]
                path, params=params, headers=extra_headers
            )

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code in (401, 403) and attempt == 0:
                logger.warning("Session expired; re-authenticating …")
                await self._login()
                continue

            resp.raise_for_status()

        raise RuntimeError("Failed after re-authentication")

    # ------------------------------------------------------------------ #
    # Public methods                                                       #
    # ------------------------------------------------------------------ #

    async def search_meters(
        self, q: str = "", page: int = 1
    ) -> dict[str, Any]:
        """
        Search meters by meter-ID or serial number.
        Returns {total, page, data: [{meterId, serialNo, make, phaseType,
                                      installStatus, dtCode}]}
        """
        raw = await self._get(
            "/portal/meters/search", params={"q": q, "page": page}
        )
        return raw

    async def get_meter_detail(self, meter_id: str) -> dict[str, Any]:
        """
        Nameplate + hierarchy for one meter, via SvelteKit __data.json.
        Decodes the compact reference-indexed SvelteKit format.
        """
        raw = await self._get(f"/meters/{meter_id}/__data.json")
        return _decode_meter_data_node(raw)

    async def get_meter_geo(self, meter_id: str) -> dict[str, Any]:
        """Latitude/longitude for one meter."""
        raw = await self._get(f"/portal/meters/{meter_id}/geo")
        return raw["data"]

    async def get_meter_energy(self, meter_id: str) -> list[dict[str, Any]]:
        """
        Consumption readings for one meter.
        Returns list of {timestamp, kwh, kvah, voltR}.
        """
        raw = await self._get(f"/portal/meters/{meter_id}/energy")
        return raw["data"]

    async def list_dts(self, page: int = 1) -> dict[str, Any]:
        """
        List distribution transformers.
        Returns {total, data: [{code, name, feederCode, capacityKva}]}
        """
        return await self._get("/portal/dts", params={"page": page})

    async def export_meters(self) -> list[dict[str, Any]]:
        """
        Bulk export of all meters (requires HMAC signing).
        Returns all meters with hierarchy + geo in one call.
        """
        raw = await self._get(
            "/portal/export", params={"page": 1}, signed=True
        )
        return raw["data"]

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# ------------------------------------------------------------------ #
# SvelteKit __data.json decoder                                        #
# ------------------------------------------------------------------ #

def _decode_meter_data_node(raw: dict) -> dict[str, Any]:
    """
    The SvelteKit __data.json format packs data as a flat list where
    values can be indices into that same list (to deduplicate strings).
    The first element of `data` is a root object whose values are indices.

    We resolve them into a clean Python dict.
    """
    nodes = raw.get("nodes", [])
    # Node 0 = root layout, Node 1 = auth layout, Node 2 = page data
    for node in reversed(nodes):
        if node and node.get("type") == "data" and "uses" in node and node["uses"].get("params"):
            return _resolve_node(node)
    return {}


def _resolve_node(node: dict) -> dict:
    data: list = node["data"]
    if not data:
        return {}

    def resolve(val):
        if isinstance(val, int) and 0 <= val < len(data):
            inner = data[val]
            if isinstance(inner, (dict, list)):
                return resolve_obj(inner)
            return inner
        if isinstance(val, (dict, list)):
            return resolve_obj(val)
        return val

    def resolve_obj(obj):
        if isinstance(obj, dict):
            return {k: resolve(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [resolve(v) for v in obj]
        return obj

    root = data[0]
    if isinstance(root, dict):
        return resolve_obj(root)
    return {"data": resolve(root)}
