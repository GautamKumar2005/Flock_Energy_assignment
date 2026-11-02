# Urja Meter Ops — Reverse Engineering & Protocol Specification (`PROTOCOL.md`)

## 1. Executive Summary

The **Urja Meter Ops** internal portal (`https://urja-ops.flockenergy.tech`) is built as a single-page / server-rendered application using **SvelteKit** and **better-auth** for session management. While the portal provides no documented external API, under the hood it consumes a combination of JSON REST endpoints, SvelteKit serialized internal data streams (`__data.json`), and an HMAC-SHA256 protected bulk export route.

This document details how the portal works under the hood, how authentication is negotiated, how data is fetched and formatted, and the quirks and surprises discovered during protocol analysis.

---

## 2. Authentication & Session Management

### Login Mechanism
- **Endpoint**: `POST https://urja-ops.flockenergy.tech/login`
- **Content-Type**: `application/x-www-form-urlencoded`
- **Parameters**: `email` and `password`
- **Required Headers**: `Origin: https://urja-ops.flockenergy.tech`, `Referer: https://urja-ops.flockenergy.tech/login`

### Session Lifecycle
Upon a successful login with operator credentials (`operator@urja.local` / `urja-ops-2026`), the backend issues an HTTP-only session cookie (managed by `better-auth`). Subsequent requests must carry this cookie.

### Session Resilience
The portal session can expire or be invalidated. Our client handles this transparently:
1. When any request encounters an HTTP `401 Unauthorized` or `403 Forbidden`, the client automatically traps the response.
2. It executes a seamless re-login handshake using cached credentials.
3. It refreshes the session cookie and replays the original request without surfacing errors to API consumers.

---

## 3. Discovered Endpoints & Protocol Analysis

### 3.1 Meter Search (`/portal/meters/search`)
- **Method**: `GET`
- **Query Params**: `q={search_term}&page={page_num}`
- **Response Format**:
  ```json
  {
    "total": 403,
    "page": 1,
    "data": [
      {
        "meterId": "J100000",
        "serialNo": "SE33962",
        "make": "HPL",
        "phaseType": "single",
        "installStatus": "Decommissioned",
        "dtCode": "DT-001"
      }
    ]
  }
  ```
- **Quirks**: The search operates as a prefix / substring match on `meterId` and `serialNo`. It paginates 20 results per page.

---

### 3.2 Individual Meter Detail (`/meters/{meter_id}/__data.json`)
The human portal does not load meter nameplate and hierarchy from a standard REST endpoint; instead, SvelteKit uses internal route data serialization (`__data.json`).

- **Method**: `GET`
- **Path**: `/meters/{meter_id}/__data.json`
- **Payload Structure**: SvelteKit serializes data as a flat array of nodes where objects and lists reference primitive strings and sub-objects by integer index into the array (reference deduplication):
  ```json
  {
    "type": "data",
    "nodes": [
      null,
      null,
      {
        "type": "data",
        "data": [
          {"meterId": 1, "detail": 2, "hierarchy": 3},
          "J100000",
          {"data": 4},
          {"Zone": 5, "DT": 6},
          [{"parameterName": 7, "parameterValue": 8}],
          "Jaipur Zone 1 (Z-01)",
          "DT-001",
          "Make",
          "HPL"
        ]
      }
    ]
  }
  ```
- **Decoder Implementation**: We implemented `_decode_meter_data_node()` in `portal_client.py` which recursively dereferences all indices against `data[]` into clean nested dictionaries and arrays.
- **Quirks**: For non-existent meter IDs, the endpoint returns HTTP `200` with an empty data node `{}` instead of `404 Not Found`. Our API detects this and translates it to standard HTTP `404`.

---

### 3.3 Meter Geolocation (`/portal/meters/{meter_id}/geo`)
- **Method**: `GET`
- **Response**:
  ```json
  {
    "status": "success",
    "data": {
      "latitude": "26.938961002479868",
      "longitude": "75.83095696146852"
    }
  }
  ```
- **Quirks**: The coordinates are returned as **strings**, not numbers. Our API casts them to IEEE 754 floating point numbers (`float`).

---

### 3.4 Consumption Readings (`/portal/meters/{meter_id}/energy`)
- **Method**: `GET`
- **Response**:
  ```json
  {
    "status": "success",
    "data": [
      {
        "timestamp": "23/06/2026 23:30",
        "kwh": "48438.74",
        "kvah": "52313.84",
        "voltR": "226"
      }
    ]
  }
  ```
- **Quirks**:
  - `timestamp` is formatted in non-standard `DD/MM/YYYY HH:MM`.
  - Energy readings (`kwh`, `kvah`) and voltage (`voltR`) are serialized as strings.
  - Up to ~337 historical 30-minute interval readings are returned per meter.

---

### 3.5 Distribution Transformers (`/portal/dts`)
- **Method**: `GET`
- **Query Params**: `page={page_num}`
- **Response**:
  ```json
  {
    "total": 40,
    "page": 1,
    "data": [
      {
        "code": "DT-001",
        "name": "Malviya Nagar DT 1",
        "feederCode": "F-001",
        "capacityKva": 250
      }
    ]
  }
  ```

---

### 3.6 Bulk Export & Cryptographic HMAC Signing (`/portal/export` & `/portal/keys`)

The portal frontend bundles JavaScript containing an administrative export workflow. This represents the fastest bulk path to extract the complete meter fleet.

#### Key Discovery
- **Endpoint**: `GET /portal/keys`
- **Response**:
  ```json
  {
    "data": {
      "signingSecret": "<hex_secret_string>"
    }
  }
  ```

#### HMAC Signature Algorithm
Requests to `/portal/export` fail with `401 / 403` unless authenticated with two custom HTTP headers:
- `x-timestamp`: Unix epoch timestamp in seconds (`str(int(time.time()))`).
- `x-signature`: HMAC-SHA256 hex digest computed over a canonicalized message.

**Canonical Message Format**:
```
METHOD\nPATH\nQUERY\nTIMESTAMP
```
*Example*:
```
GET
/portal/export
page=1
1793648000
```

**Signature Calculation (Python)**:
```python
import hashlib, hmac

message = f"{method.upper()}\n{path}\n{query}\n{timestamp}"
signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
```

#### Export Response
The export endpoint returns all **403 smart meters** in a single call, complete with their nameplate parameters, full 7-level hierarchy, and coordinates:
```json
{
  "total": 403,
  "data": [
    {
      "meterId": "J100000",
      "serialNo": "SE33962",
      "make": "HPL",
      "phaseType": "single",
      "installStatus": "Decommissioned",
      "installType": "Whole Current",
      "build": "legacy",
      "dtCode": "DT-001",
      "hierarchy": {
        "zone": { "name": "Jaipur Zone 1", "code": "Z-01" },
        "circle": { "name": "Circle 1", "code": "C-01" },
        "division": { "name": "Division 1", "code": "D-01" },
        "subdivision": { "name": "Subdivision 1", "code": "SD-01" },
        "substation": { "name": "Substation 1", "code": "SS-01" },
        "feeder": { "name": "Feeder 1", "code": "F-001" },
        "dt": { "name": "Malviya Nagar DT 1", "code": "DT-001" }
      },
      "geo": {
        "lat": 26.938961002479868,
        "lng": 75.83095696146852
      }
    }
  ]
}
```
*Quirks in Export Payload*:
- The coordinates use keys `lat` and `lng`, whereas `/portal/meters/{id}/geo` uses `latitude` and `longitude`.
- Numbers are IEEE floats in the export payload, but strings in the individual geo endpoint.

---

## 4. Discovered Quirks, Surprises, and Mitigations

| Quirk / Anomaly | Portal Behavior | Our Clean API Mitigation |
| :--- | :--- | :--- |
| **Silent 404s** | Returns `200 OK` with `{}` for invalid meter IDs | Validates payload presence and returns explicit `404 Not Found` with clear error message |
| **Mixed Coordinate Schemas** | Uses `lat`/`lng` in `/export`, but `latitude`/`longitude` in `/geo` | Normalizes all coordinates into `MeterGeo(latitude=..., longitude=...)` |
| **String Numbers** | Readings, voltages, and coordinates returned as strings | Parsed and validated via Pydantic models with strict typing |
| **SvelteKit Deduplication** | Employs index pointer graph (`uses`, `data[]`) | Custom recursive resolver reconstructs full tree hierarchy cleanly |
| **HMAC Time Drift** | `/export` rejects timestamps that drift beyond tolerance | Synchronizes local system clock and re-computes `x-timestamp` per request |
| **Single-Phase vs Three-Phase Casing** | Uses lowercase `"single"` / `"three"` in search, capitalized in UI | Standardized in schema enums |
