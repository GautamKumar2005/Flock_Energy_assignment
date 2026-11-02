# Urja Meter Ops API & Intelligence Platform ⚡

A high-performance, resilient, and fully documented REST API and modern web client built over the legacy **Urja Meter Ops** utility distribution portal.

This service abstracts the aging internal portal into a clean, strongly-typed OpenAPI 3.1 compliant service that external programs, data pipelines, and product teams can consume without ever interacting with the original portal.

---

## 🚀 Key Highlights & Capabilities

- **Clean REST API**: Strongly typed Pydantic models decoupling upstream portal quirks from external consumers.
- **Reverse-Engineered HMAC Bulk Export**: Discovered and implemented the portal's internal HMAC-SHA256 signature algorithm (`/portal/export` via `/portal/keys`), extracting all 403 meters in a single bulk call.
- **SvelteKit `__data.json` Recursive Decoder**: Decodes SvelteKit's internal reference-deduplicated data format into clean nested JSON.
- **Local Index & Spatial Query Layer**:
  - **Geospatial Radius Queries**: Haversine distance search (`/meters/nearby?lat=...&lon=...&radius_km=...`) to answer *"which meters are near this location?"*
  - **Multi-Attribute Filter Studio**: Filter meters simultaneously across manufacturer (`make`), `phase_type`, `install_status`, `dt_code`, `feeder_code`, and `zone_code`.
  - **Instant Fleet Analytics**: Aggregated network statistics (`/meters/stats`) covering phase splits, make distribution, and transformer load.
- **Network Topology Reconstructor**: Reconstructs the 7-level hierarchy tree: `Zone → Circle → Division → Subdivision → Substation → Feeder → DT → Meters`.
- **Intelligent Caching & Freshness**: 10-minute warm TTL index with on-demand `/sync` endpoint and graceful fallback if the portal slows down or fails.
- **Robust Session Resilience**: Automatic detection of expired sessions (`401/403`) with transparent re-login and request replay.
- **Modern Web Client**: Interactive dark-mode dashboard embedded at `/` featuring Leaflet GIS mapping, Chart.js time-series consumption graphs, and hierarchy visualizer.
- **Comprehensive Test Suite**: 16 automated pytest tests verifying cryptographic signatures, decoders, spatial calculations, and API endpoints.

---

## 📂 Project Structure

```
flock/
├── src/
│   └── urja_api/
│       ├── __init__.py          # Package initialization
│       ├── main.py              # FastAPI application, routing, lifespan, middleware
│       ├── models.py            # Pydantic schemas (Clean API contract)
│       ├── portal_client.py     # Portal client (Auth, SvelteKit decoder, HMAC signing)
│       ├── store.py             # Local index, Haversine spatial queries, caching
│       └── dashboard.py         # Modern Web Client single-page dashboard (HTML/CSS/JS)
├── tests/
│   └── test_api.py              # Comprehensive automated pytest test suite (16 tests)
├── js_analysis/                 # Decompiled JavaScript analysis from portal bundle
├── explore.py                   # Protocol reverse-engineering test script
├── openapi.json                 # Exported OpenAPI 3.1 specification
├── PROTOCOL.md                  # Detailed reverse-engineering writeup & protocol analysis
├── REFLECTION.md                # Engineering reflection answering the 5 evaluation questions
├── pyproject.toml               # Modern PEP 517 build configuration
└── README.md                    # Project documentation (this file)
```

---

## 🛠️ Quickstart: Installation & Running

### Prerequisites
- Python 3.11+
- pip

### 1. Install Dependencies
```bash
cd flock
pip install -e .
```
*(Optional dev dependencies for running tests: `pip install -e ".[dev]"`)*

### 2. Start the Service
```bash
python -m uvicorn urja_api.main:app --host 0.0.0.0 --port 8000 --reload
```
The server will start at `http://localhost:8000`.

### 3. Explore the Service
- **Modern Web Client Dashboard**: [http://localhost:8000/](http://localhost:8000/)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Raw OpenAPI Spec**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 🧪 Running Automated Tests

Run the complete test suite:
```bash
python -m pytest -v
```
All 16 tests will run against live endpoints, decoders, spatial math, and error handlers:
```
tests/test_api.py::test_hmac_signature_generation PASSED
tests/test_api.py::test_sveltekit_decoder_reference_resolution PASSED
tests/test_api.py::test_haversine_distance PASSED
tests/test_api.py::test_health_check PASSED
tests/test_api.py::test_api_index PASSED
tests/test_api.py::test_dashboard_html_rendering PASSED
tests/test_api.py::test_network_stats PASSED
tests/test_api.py::test_meters_list PASSED
tests/test_api.py::test_meters_query_filter PASSED
tests/test_api.py::test_meters_nearby_spatial_search PASSED
tests/test_api.py::test_get_meter_detail PASSED
tests/test_api.py::test_get_meter_energy PASSED
tests/test_api.py::test_transformers_list PASSED
tests/test_api.py::test_network_hierarchy PASSED
tests/test_api.py::test_sync_status PASSED
tests/test_api.py::test_not_found_meter PASSED
======================= 16 passed in 8.00s =======================
```

---

## 📡 Sample API Requests

### 1. Find Meters Near a Location (Geospatial Radius Search)
```bash
curl -X GET "http://localhost:8000/meters/nearby?lat=26.9389&lon=75.8309&radius_km=3&limit=5"
```
**Response**:
```json
{
  "center_latitude": 26.9389,
  "center_longitude": 75.8309,
  "radius_km": 3.0,
  "count": 11,
  "meters": [
    {
      "meter_id": "J100000",
      "serial_no": "SE33962",
      "make": "HPL",
      "phase_type": "single",
      "install_status": "Decommissioned",
      "dt_code": "DT-001",
      "latitude": 26.938961,
      "longitude": 75.830957,
      "distance_km": 0.007
    }
  ]
}
```

### 2. Multi-Attribute Filter Query
```bash
curl -X GET "http://localhost:8000/meters/query?make=HPL&phase_type=single&install_status=Commissioned&page=1&page_size=2"
```

### 3. Get Meter Details & Hierarchy
```bash
curl -X GET "http://localhost:8000/meters/J100000"
```

### 4. Fetch Time-Series Consumption Readings
```bash
curl -X GET "http://localhost:8000/meters/J100000/energy"
```

### 5. Fetch Network Fleet Stats
```bash
curl -X GET "http://localhost:8000/meters/stats"
```

### Python SDK Example
```python
import httpx

with httpx.Client(base_url="http://localhost:8000") as client:
    # 1. Nearby meters query
    nearby = client.get("/meters/nearby", params={"lat": 26.9389, "lon": 75.8309, "radius_km": 5}).json()
    print(f"Found {nearby['count']} meters nearby")

    # 2. Get energy consumption readings
    readings = client.get(f"/meters/{nearby['meters'][0]['meter_id']}/energy").json()
    print(f"Latest reading: {readings[0]}")
```

---

## 📐 Architecture & Key Design Decisions

```
+-------------------------------------------------------------------------+
|                         Consumer Applications                           |
|       (Data Pipelines, ML Models, Mobile Field Apps, Web Dashboard)     |
+-------------------------------------------------------------------------+
                                    │
                                    ▼ HTTP (REST / OpenAPI 3.1)
+-------------------------------------------------------------------------+
|                          Urja Meter Ops API                             |
|  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────┐  |
|  |  FastAPI Router     |  |  Pydantic Contract  |  | Modern Web App  |  |
|  |  (/meters, /nearby) |  |  Models Validation  |  | (Dashboard SPA) |  |
|  └──────────┬──────────┘  └──────────┬──────────┘  └─────────────────┘  |
|             │                        │                                  |
|             ▼                        ▼                                  |
|  ┌───────────────────────────────────────────────────────────────────┐  |
|  |                Local Index & Spatial Query Layer                  |  |
|  |  • Haversine Spatial Bounding      • Multi-Attribute Filtering    |  |
|  |  • In-Memory Fast Cache (TTL=600s) • Network Topology Tree Cache  |  |
|  └───────────────────────────────────┬───────────────────────────────┘  |
|                                      │                                  |
|                                      ▼                                  |
|  ┌───────────────────────────────────────────────────────────────────┐  |
|  |                    Urja Portal Client Layer                       |  |
|  |  • Session Cookie Manager          • SvelteKit __data Decoder     |  |
|  |  • Re-Auth Circuit on 401/403      • HMAC-SHA256 Canonical Signer |  |
|  └───────────────────────────────────┬───────────────────────────────┘  |
+--------------------------------------│----------------------------------+
                                       │ HTTPS Session / HMAC Headers
                                       ▼
+-------------------------------------------------------------------------+
|                  Legacy Urja Meter Ops Web Portal                       |
|   https://urja-ops.flockenergy.tech  (SvelteKit / better-auth session)  |
+-------------------------------------------------------------------------+
```

### 1. Two-Tiered Data Access Architecture
- **Real-Time Point Lookups**: Endpoints like `/meters/{id}/energy` directly query the upstream portal because interval consumption readings change frequently.
- **Cached In-Memory Local Index**: Network topology, transformers, coordinates, and nameplate attributes are synchronized into memory using the cryptographic `/portal/export` endpoint. This gives consumers sub-millisecond response times for complex queries.

### 2. Resilient Authentication Circuit
The client does not re-authenticate before every call. It maintains an active session cookie and automatically captures `401 Unauthorized` or `403 Forbidden` responses, executes a transparent re-login handshake, and seamlessly retries the request without failing the consumer.

### 3. Graceful Degradation
If the upstream portal experiences downtime or network latency, the local index continues serving `/meters`, `/meters/query`, `/meters/nearby`, and `/network` from the last known good state.

---

## 📈 Scale Analysis: At What Scale Does This Struggle?

Our in-memory spatial index and Python dictionary store are optimized for speed, simplicity, and low memory overhead.
- **Current Scale (403 meters)**: Memory footprint is **~4 MB**; spatial searches execute in **< 1 millisecond**.
- **At 50,000 meters**: Memory footprint would be **~150 MB**. Linear scan with Haversine distance would take ~15–25ms per query, which is still viable for small deployments.
- **At What Scale It Struggles (100,000+ meters)**:
  1. **Linear Haversine Scan**: Calculating trigonometric distances across 100k+ meters on every request consumes significant CPU and introduces latency bottlenecks.
  2. **Multi-Worker Memory Duplication**: In multi-process production servers (`gunicorn -w 8`), each worker would duplicate the full memory index.
  3. **Re-sync Payload Size**: Downloading a 100k-record JSON payload from `/portal/export` in a single HTTP request would risk network timeouts and heavy garbage collection spikes.

### What We Would Change at Scale (1,000,000+ Meters):
1. **Database Spatial Indexing (PostGIS / SQLite R*Tree)**: Migrate the in-memory array to PostgreSQL with PostGIS or embedded DuckDB/SQLite with `RTREE`. Geospatial queries become $O(\log N)$ bounding-box index scans (`ST_DWithin`).
2. **Cursor-Based Stream Synchronization**: Replace the single `/portal/export` payload with paginated or delta-timestamped sync (`updated_since=...`).
3. **Redis Shared Cache**: Decouple cache storage from Python process memory using Redis geo-sets (`GEOADD` / `GEORADIUS`), allowing horizontal scaling of stateless API workers.

---

## 🔄 Freshness & Caching Policy

| Data Category | Freshness Strategy | Invalidation Policy |
| :--- | :--- | :--- |
| **Fleet Nameplates & Geo** | In-Memory Local Index | **10-minute TTL** (`ttl_seconds=600`). Triggered on demand via `POST /sync`. |
| **Network Hierarchy** | Cached Tree | Synchronized with bulk export; invalidated whenever a sync occurs. |
| **Energy Consumption** | Direct Upstream Proxy | Real-time on every request (ensuring zero lag on meter readings). |
| **Signing Secret** | In-Memory String | Cached per session; cleared upon re-login. |

---

## ⚠️ What Was Intentionally Skipped & Trade-Offs

1. **Persistent External Database**: We intentionally chose not to require external dependencies like PostgreSQL or Redis so the entire service can be cloned, installed, and run locally with zero infrastructure friction.
2. **Write / Mutation Endpoints**: The portal was treated as strictly read-only. We avoided any reverse-engineered write operations to ensure complete safety for utility operations.
3. **Complex Frontend Framework Toolchains**: The modern web client is built with pure Vanilla JavaScript, modern CSS, Leaflet, and Chart.js served directly from FastAPI, eliminating the need for `npm run build` or Node.js runtimes.

---

## 🔗 Submission Deliverables & Documentation

- 📄 [PROTOCOL.md](file:///C:/Users/gauta/flock_energy/flock/PROTOCOL.md) — Comprehensive technical write-up of portal discovery, authentication, SvelteKit decoding, and HMAC signing.
- 📄 [REFLECTION.md](file:///C:/Users/gauta/flock_energy/flock/REFLECTION.md) — Engineering reflection answering the 5 take-home evaluation questions.
- 📋 [openapi.json](file:///C:/Users/gauta/flock_energy/flock/openapi.json) — OpenAPI 3.1 specification.
- 🧪 [tests/test_api.py](file:///C:/Users/gauta/flock_energy/flock/tests/test_api.py) — Automated test suite with 16 passing tests.
