"""
Test suite for Urja Meter Ops API.
Tests client authentication, HMAC signing, SvelteKit decoders, FastAPI endpoints,
geospatial queries, network hierarchy reconstruction, and error handling.
"""
from __future__ import annotations

import pytest
import httpx
from fastapi.testclient import TestClient

from urja_api.main import app, _shape_meter_summary
from urja_api.portal_client import _sign, _decode_meter_data_node
from urja_api.store import haversine_km, LocalIndexStore


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


# --------------------------------------------------------------------------- #
# 1. Cryptographic and Signing Tests                                          #
# --------------------------------------------------------------------------- #


def test_hmac_signature_generation():
    method = "GET"
    path = "/portal/export"
    query = "page=1"
    secret = "test-secret-key-12345"

    timestamp, signature = _sign(method, path, query, secret)
    assert len(timestamp) >= 10
    assert len(signature) == 64  # SHA-256 hex digest length
    assert all(c in "0123456789abcdef" for c in signature)


# --------------------------------------------------------------------------- #
# 2. SvelteKit __data.json Decoder Tests                                      #
# --------------------------------------------------------------------------- #


def test_sveltekit_decoder_reference_resolution():
    # SvelteKit encodes data where values are indices into a shared flat array
    mock_payload = {
        "type": "data",
        "nodes": [
            None,
            None,
            {
                "type": "data",
                "uses": {"params": ["id"]},
                "data": [
                    {"meterId": 1, "detail": 2, "hierarchy": 3},
                    "J100000",
                    {"data": 4},
                    {"Zone": 5, "Circle": 6},
                    [{"parameterName": 7, "parameterValue": 8}],
                    "Jaipur Zone 1 (Z-01)",
                    "Circle 1 (C-01)",
                    "Make",
                    "HPL",
                ],
            },
        ],
    }

    decoded = _decode_meter_data_node(mock_payload)
    assert decoded["meterId"] == "J100000"
    assert decoded["hierarchy"]["Zone"] == "Jaipur Zone 1 (Z-01)"
    assert decoded["hierarchy"]["Circle"] == "Circle 1 (C-01)"
    assert decoded["detail"]["data"][0]["parameterName"] == "Make"
    assert decoded["detail"]["data"][0]["parameterValue"] == "HPL"


# --------------------------------------------------------------------------- #
# 3. Spatial Math & Haversine Tests                                           #
# --------------------------------------------------------------------------- #


def test_haversine_distance():
    # Jaipur center to nearby point (~1.1 km)
    lat1, lon1 = 26.9124, 75.7873
    lat2, lon2 = 26.9224, 75.7873
    dist = haversine_km(lat1, lon1, lat2, lon2)
    assert 1.0 < dist < 1.2

    # Same point distance should be zero
    assert haversine_km(lat1, lon1, lat1, lon1) == 0.0


# --------------------------------------------------------------------------- #
# 4. API Endpoints Tests                                                      #
# --------------------------------------------------------------------------- #


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "urja-api"
    assert data["version"] == "1.0.0"


def test_api_index(client: TestClient):
    response = client.get("/api")
    assert response.status_code == 200
    data = response.json()
    assert "dashboard" in data
    assert "docs_swagger" in data
    assert "openapi_spec" in data


def test_dashboard_html_rendering(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Urja Meter Ops" in response.text
    assert "Leaflet" in response.text
    assert "Chart.js" in response.text


def test_network_stats(client: TestClient):
    response = client.get("/meters/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_meters"] > 0
    assert data["total_dts"] > 0
    assert "makes_breakdown" in data
    assert "statuses_breakdown" in data
    assert "phases_breakdown" in data


def test_meters_list(client: TestClient):
    response = client.get("/meters?page=1")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "data" in data
    assert len(data["data"]) <= 20
    if data["data"]:
        meter = data["data"][0]
        assert "meter_id" in meter
        assert "make" in meter
        assert "phase_type" in meter


def test_meters_query_filter(client: TestClient):
    # Filter by make
    response = client.get("/meters/query?make=HPL&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert all(m["make"] == "HPL" for m in data["data"])

    # Filter by phase
    response_phase = client.get("/meters/query?phase_type=single&page_size=10")
    assert response_phase.status_code == 200
    data_phase = response_phase.json()
    assert all(m["phase_type"] == "single" for m in data_phase["data"])


def test_meters_nearby_spatial_search(client: TestClient):
    # Search around Jaipur center
    response = client.get("/meters/nearby?lat=26.9389&lon=75.8309&radius_km=5&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "meters" in data
    assert len(data["meters"]) <= 10
    # Distances should be sorted in ascending order
    distances = [m["distance_km"] for m in data["meters"]]
    assert distances == sorted(distances)


def test_get_meter_detail(client: TestClient):
    response = client.get("/meters/J100000")
    assert response.status_code == 200
    data = response.json()
    assert data["meter_id"] == "J100000"
    assert "nameplate" in data
    assert "hierarchy" in data


def test_get_meter_energy(client: TestClient):
    response = client.get("/meters/J100000/energy")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        reading = data[0]
        assert "timestamp" in reading
        assert "kwh" in reading
        assert "volt_r" in reading


def test_transformers_list(client: TestClient):
    response = client.get("/transformers?page=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert len(data["data"]) > 0
    dt = data["data"][0]
    assert "code" in dt
    assert "name" in dt
    assert "capacity_kva" in dt


def test_network_hierarchy(client: TestClient):
    response = client.get("/network")
    assert response.status_code == 200
    data = response.json()
    assert "zones" in data
    assert "total_meters" in data
    assert len(data["zones"]) > 0
    first_zone = data["zones"][0]
    assert "circles" in first_zone


def test_sync_status(client: TestClient):
    response = client.get("/sync/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "uninitialized")
    assert data["total_meters"] > 0
    assert data["ttl_seconds"] == 600


def test_not_found_meter(client: TestClient):
    response = client.get("/meters/NON_EXISTENT_METER_999999")
    assert response.status_code == 404
