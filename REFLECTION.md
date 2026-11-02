# Engineering Reflection (`REFLECTION.md`)

### 1. What assumptions did you make?
- **Portal Read-Only Contract**: Assumed all upstream interactions are strictly non-mutating (safe `GET` queries). We did not attempt any data modifications, respecting utility ops safety.
- **Data Scale**: Assumed the current deployment represents a mid-scale distribution division (~403 meters across 40 distribution transformers in Jaipur Zone 1). This informed our decision to hold a warm in-memory index rather than spinning up an external database like PostgreSQL/PostGIS or Redis.
- **Session Expiry Tolerance**: Assumed the portal session token (`better-auth`) has a rolling TTL. We designed the client to handle automatic re-authentication upon `401/403` HTTP codes rather than preemptively pinging `/login` before every single request.
- **Coordinates Coordinate Reference System**: Assumed geographic coordinates (`lat`/`lng`) are WGS 84 (standard EPSG:4326), suitable for great-circle spherical distance calculations via the Haversine formula.

---

### 2. Which part was the most difficult, and how did you get unstuck?
- **The Challenge**: The most elusive part was discovering how the portal's `/portal/export` endpoint verified requests. Direct HTTP requests returned `401/403` despite carrying valid session cookies.
- **How I Got Unstuck**:
  1. I extracted and decompiled the client-side JavaScript chunks (`js_analysis/nodes_5.*.js`) loaded by the SvelteKit application.
  2. Searching for `/portal/export` in the bundle led directly to an internal signing routine that called `GET /portal/keys` to retrieve `signingSecret`.
  3. Inspecting the function revealed an HMAC-SHA256 signature calculated over `METHOD\nPATH\nQUERY\nTIMESTAMP` and passed in `x-signature` and `x-timestamp` headers.
  4. Implementing and validating this signing algorithm in Python unlocked the bulk export endpoint, returning the complete 403-meter dataset with full hierarchy and geospatial coordinates in one request.

---

### 3. If you had another day, what would you improve?
- **SQLite / DuckDB Persistent Vector & Spatial Storage**: Migrate the in-memory dictionary index to an embedded SQLite database using `R*Tree` spatial index or DuckDB with geospatial extensions. This would preserve instant cold-starts across process restarts and scale to 1,000,000+ meters effortlessly.
- **WebSocket / SSE Live Consumption Streaming**: Add real-time Server-Sent Events (SSE) or WebSocket feeds for live smart meter telemetry streaming (e.g. streaming voltage fluctuations or interval load profiles to the modern web client).
- **Background Cron Sync Job**: Implement an asynchronous background worker using `APScheduler` or FastAPI background tasks that proactively refreshes the local index right before the 10-minute TTL expires, ensuring zero user-facing latency.
- **Prometheus Metrics & Structured Audit Logging**: Add an `/audit` or `/metrics` endpoint exporting request latencies, portal upstream latency, cache hit/miss rates, and re-authentication counters.

---

### 4. What mistake did you make while solving this (there's always one)?
- **The SvelteKit `200 OK` on Missing Resources**: When testing meter lookups for non-existent IDs (e.g. `NON_EXISTENT_METER_999999`), our initial client assumed the portal would return an HTTP `404 Not Found`. Instead, SvelteKit returned HTTP `200 OK` with an empty data node `{}`.
- **The Consequence**: Our endpoint was initially constructing an empty `MeterDetail` and returning `200 OK` instead of `404 Not Found`.
- **The Fix**: During automated pytest verification, this edge case was immediately surfaced by `test_not_found_meter`. I patched `get_meter()` to validate that `raw_detail` contains a non-empty `meterId` (and verified against the local index store) before raising an explicit HTTP `404 Not Found`.
- **Second Glitch**: In `pyproject.toml`, the initial build-backend string was set to `setuptools.backends.legacy:build` instead of the standard PEP 517 `setuptools.build_meta`, causing `pip install -e .` to raise a `BackendUnavailable` error. Correcting this to `setuptools.build_meta` solved the packaging setup cleanly.

---

### 5. If you were reviewing your own submission, what would you criticise?
- **Coupling of Single-Instance Client State**: The shared `_client` and `_store` are currently held as module singletons in `main.py`. In a multi-worker production deployment (e.g. `gunicorn -w 4`), each worker maintains its own in-memory index rather than sharing a unified Redis/Memcached cache. While appropriate for a standalone service, introducing Redis or a centralized cache layer would be cleaner for horizontally scaled deployments.
- **Static Dashboard Bundling**: The web dashboard is currently embedded in `dashboard.py` as a raw multiline HTML string to avoid requiring users to run complex npm/vite toolchains. While this makes running the application painless (`pip install -e . && uvicorn urja_api.main:app`), in a large production engineering team, the frontend would live in its own repository with TypeScript and automated E2E Cypress/Playwright tests.
