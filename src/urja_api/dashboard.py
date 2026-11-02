"""
Embedded Modern Web Client for Urja Meter Ops.
Serves a responsive, dark-mode single-page dashboard with Leaflet GIS mapping,
Chart.js consumption analytics, network hierarchy explorer, and real-time filters.
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Urja Meter Ops 2.0 | Next-Gen Utility Intelligence</title>
  <!-- Google Fonts: Inter -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <!-- Leaflet CSS -->
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
  <!-- Leaflet JS -->
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <!-- Chart.js -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

  <style>
    :root {
      --bg-base: #0a0d14;
      --bg-surface: #121824;
      --bg-surface-elevated: #1a2332;
      --border-subtle: #232e42;
      --border-focus: #3b82f6;
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --accent-blue: #38bdf8;
      --accent-indigo: #6366f1;
      --accent-green: #10b981;
      --accent-amber: #f59e0b;
      --accent-rose: #f43f5e;
      --radius-sm: 8px;
      --radius-md: 12px;
      --radius-lg: 16px;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg-base);
      color: var(--text-main);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      line-height: 1.5;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    header {
      background: rgba(18, 24, 36, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border-subtle);
      padding: 16px 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 1000;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .brand-icon {
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, var(--accent-blue), var(--accent-indigo));
      border-radius: var(--radius-sm);
      display: grid;
      place-items: center;
      font-weight: 800;
      color: #fff;
      font-size: 1.1rem;
    }

    .brand-title {
      font-size: 1.15rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }

    .brand-badge {
      background: rgba(56, 189, 248, 0.12);
      color: var(--accent-blue);
      border: 1px solid rgba(56, 189, 248, 0.25);
      font-size: 0.72rem;
      padding: 2px 8px;
      border-radius: 9999px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .nav-links {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .nav-link {
      color: var(--text-muted);
      text-decoration: none;
      font-size: 0.88rem;
      font-weight: 500;
      padding: 6px 12px;
      border-radius: var(--radius-sm);
      transition: all 0.15s ease;
    }

    .nav-link:hover {
      color: var(--text-main);
      background: var(--bg-surface-elevated);
    }

    .btn-sync {
      background: linear-gradient(135deg, #2563eb, #3b82f6);
      color: white;
      border: none;
      padding: 8px 16px;
      border-radius: var(--radius-sm);
      font-weight: 600;
      font-size: 0.85rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: opacity 0.2s;
    }

    .btn-sync:hover {
      opacity: 0.9;
    }

    main {
      padding: 24px 28px;
      max-width: 1600px;
      margin: 0 auto;
      width: 100%;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    /* KPI Grid */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
    }

    .kpi-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 20px;
      position: relative;
      overflow: hidden;
      transition: transform 0.2s, border-color 0.2s;
    }

    .kpi-card:hover {
      transform: translateY(-2px);
      border-color: rgba(56, 189, 248, 0.4);
    }

    .kpi-label {
      font-size: 0.8rem;
      color: var(--text-muted);
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .kpi-value {
      font-size: 2rem;
      font-weight: 800;
      color: var(--text-main);
      margin-top: 6px;
      letter-spacing: -0.03em;
    }

    .kpi-sub {
      font-size: 0.78rem;
      color: var(--text-dim);
      margin-top: 4px;
    }

    /* Main Grid Layout */
    .dashboard-layout {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 24px;
    }

    @media (max-width: 1100px) {
      .dashboard-layout {
        grid-template-columns: 1fr;
      }
    }

    .card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .card-header {
      padding: 16px 20px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .card-title {
      font-size: 1rem;
      font-weight: 700;
      letter-spacing: -0.01em;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    /* Map container */
    #map {
      height: 480px;
      width: 100%;
      background: #0d1117;
    }

    /* Filter Bar */
    .filter-bar {
      padding: 16px 20px;
      background: var(--bg-surface-elevated);
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
    }

    .search-input {
      background: var(--bg-base);
      border: 1px solid var(--border-subtle);
      color: var(--text-main);
      padding: 8px 14px;
      border-radius: var(--radius-sm);
      font-size: 0.88rem;
      min-width: 200px;
      flex-grow: 1;
      font-family: inherit;
    }

    .search-input:focus {
      outline: none;
      border-color: var(--border-focus);
    }

    .select-filter {
      background: var(--bg-base);
      border: 1px solid var(--border-subtle);
      color: var(--text-main);
      padding: 8px 12px;
      border-radius: var(--radius-sm);
      font-size: 0.85rem;
      font-family: inherit;
      cursor: pointer;
    }

    .select-filter:focus {
      outline: none;
      border-color: var(--border-focus);
    }

    /* Table */
    .table-container {
      overflow-x: auto;
      max-height: 440px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
    }

    th {
      background: var(--bg-surface-elevated);
      color: var(--text-muted);
      text-align: left;
      padding: 12px 16px;
      font-weight: 600;
      position: sticky;
      top: 0;
      z-index: 10;
      border-bottom: 1px solid var(--border-subtle);
    }

    td {
      padding: 12px 16px;
      border-bottom: 1px solid var(--border-subtle);
      color: var(--text-main);
    }

    tr:hover td {
      background: rgba(255, 255, 255, 0.02);
      cursor: pointer;
    }

    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 0.72rem;
      font-weight: 600;
    }

    .badge-active {
      background: rgba(16, 185, 129, 0.15);
      color: var(--accent-green);
      border: 1px solid rgba(16, 185, 129, 0.3);
    }

    .badge-decom {
      background: rgba(244, 63, 94, 0.15);
      color: var(--accent-rose);
      border: 1px solid rgba(244, 63, 94, 0.3);
    }

    .badge-phase-1 {
      background: rgba(56, 189, 248, 0.15);
      color: var(--accent-blue);
      border: 1px solid rgba(56, 189, 248, 0.3);
    }

    .badge-phase-3 {
      background: rgba(245, 158, 11, 0.15);
      color: var(--accent-amber);
      border: 1px solid rgba(245, 158, 11, 0.3);
    }

    /* Modal */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(8px);
      display: none;
      place-items: center;
      z-index: 2000;
      padding: 20px;
    }

    .modal-backdrop.open {
      display: grid;
    }

    .modal {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-lg);
      width: 100%;
      max-width: 900px;
      max-height: 90vh;
      overflow-y: auto;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }

    .modal-header {
      padding: 20px 24px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .modal-title {
      font-size: 1.25rem;
      font-weight: 700;
    }

    .btn-close {
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: 1.5rem;
      cursor: pointer;
      line-height: 1;
    }

    .modal-body {
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .detail-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
    }

    .detail-item {
      background: var(--bg-surface-elevated);
      padding: 12px 16px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border-subtle);
    }

    .detail-label {
      font-size: 0.72rem;
      color: var(--text-muted);
      text-transform: uppercase;
      font-weight: 600;
    }

    .detail-value {
      font-size: 0.95rem;
      color: var(--text-main);
      font-weight: 600;
      margin-top: 4px;
      font-family: 'JetBrains Mono', monospace;
    }

    /* Hierarchy Tree */
    .tree-node {
      margin-left: 14px;
      border-left: 1px dashed var(--border-subtle);
      padding-left: 12px;
      margin-top: 4px;
    }

    .tree-label {
      font-size: 0.82rem;
      color: var(--text-muted);
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 3px 0;
    }

    .tree-label:hover {
      color: var(--text-main);
    }

    .chart-container {
      height: 320px;
      width: 100%;
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <div class="brand-icon">&#x26A1;</div>
      <div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="brand-title">Urja Meter Ops</span>
          <span class="brand-badge">API Layer 2.0</span>
        </div>
      </div>
    </div>
    <div class="nav-links">
      <a href="/docs" target="_blank" class="nav-link">Interactive Swagger Docs</a>
      <a href="/openapi.json" target="_blank" class="nav-link">OpenAPI Spec</a>
      <button class="btn-sync" id="syncBtn" onclick="syncData()">&#x21bb; Sync Live Portal</button>
    </div>
  </header>

  <main>
    <!-- KPIs -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Total Smart Meters</div>
        <div class="kpi-value" id="kpiTotalMeters">--</div>
        <div class="kpi-sub">Indexed from Urja Ops portal</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Commissioned / Active</div>
        <div class="kpi-value" id="kpiActiveMeters" style="color: var(--accent-green);">--</div>
        <div class="kpi-sub">Serving live consumers</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Distribution Transformers</div>
        <div class="kpi-value" id="kpiTotalDts" style="color: var(--accent-blue);">--</div>
        <div class="kpi-sub">11kV / 415V substations</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Single / Three Phase</div>
        <div class="kpi-value" id="kpiPhases">-- / --</div>
        <div class="kpi-sub">Domestic vs Commercial split</div>
      </div>
    </div>

    <!-- Main Layout -->
    <div class="dashboard-layout">
      <!-- Left: Interactive GIS Map -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">&#x1F5FA;&#xFE0F; Geospatial Meter Network Map</div>
          <span style="font-size: 0.8rem; color: var(--text-dim);" id="mapStatus">Loading coordinates...</span>
        </div>
        <div id="map"></div>
      </div>

      <!-- Right: Hierarchy Explorer -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">&#x1F333; Network Topology Explorer</div>
          <span style="font-size: 0.75rem; color: var(--text-dim);">Zone &#x2192; Feeder &#x2192; DT &#x2192; Meters</span>
        </div>
        <div style="padding: 16px; overflow-y: auto; max-height: 480px;" id="hierarchyTree">
          <div style="color: var(--text-dim); font-size: 0.85rem;">Loading hierarchy tree...</div>
        </div>
      </div>
    </div>

    <!-- Meters Table & Studio -->
    <div class="card">
      <div class="card-header">
        <div class="card-title">&#x1F50D; Meter Explorer & Filter Studio</div>
        <div style="font-size: 0.85rem; color: var(--text-muted);" id="tableCount">Showing 0 meters</div>
      </div>

      <div class="filter-bar">
        <input type="text" id="filterQ" class="search-input" placeholder="Search by Meter ID (e.g. J100000) or Serial..." oninput="debounceFilter()">
        
        <select id="filterMake" class="select-filter" onchange="applyFilters()">
          <option value="">All Makes</option>
        </select>

        <select id="filterPhase" class="select-filter" onchange="applyFilters()">
          <option value="">All Phases</option>
          <option value="single">Single Phase</option>
          <option value="three">Three Phase</option>
        </select>

        <select id="filterStatus" class="select-filter" onchange="applyFilters()">
          <option value="">All Statuses</option>
          <option value="Commissioned">Commissioned</option>
          <option value="Decommissioned">Decommissioned</option>
          <option value="Pending">Pending</option>
        </select>
      </div>

      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Meter ID</th>
              <th>Serial Number</th>
              <th>Make</th>
              <th>Phase</th>
              <th>Status</th>
              <th>DT Code</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="metersTableBody">
            <tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--text-dim);">Loading smart meters...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </main>

  <!-- Modal for Meter Detail & Consumption Chart -->
  <div class="modal-backdrop" id="meterModal" onclick="if(event.target===this) closeModal()">
    <div class="modal">
      <div class="modal-header">
        <div class="modal-title" id="modalMeterId">Meter Details</div>
        <button class="btn-close" onclick="closeModal()">&times;</button>
      </div>
      <div class="modal-body">
        <div class="detail-grid" id="modalDetails"></div>

        <div>
          <h4 style="margin-bottom: 12px; font-size: 0.95rem; font-weight: 700;">Energy Consumption Readings (Time-Series)</h4>
          <div class="chart-container">
            <canvas id="consumptionChart"></canvas>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let allMeters = [];
    let map = null;
    let markersLayer = null;
    let chartInstance = null;
    let debounceTimer = null;

    // Initialize Map
    function initMap() {
      map = L.map('map', { zoomControl: true }).setView([26.9124, 75.7873], 12);
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 19
      }).addTo(map);
      markersLayer = L.layerGroup().addTo(map);
    }

    async function loadStats() {
      try {
        const res = await fetch('/meters/stats');
        const data = await res.json();
        document.getElementById('kpiTotalMeters').innerText = data.total_meters;
        document.getElementById('kpiActiveMeters').innerText = data.active_meters;
        document.getElementById('kpiTotalDts').innerText = data.total_dts;
        document.getElementById('kpiPhases').innerText = `${data.single_phase_meters} / ${data.three_phase_meters}`;

        // Populate makes dropdown
        const makeSelect = document.getElementById('filterMake');
        makeSelect.innerHTML = '<option value="">All Makes</option>';
        for (const [make, count] of Object.entries(data.makes_breakdown)) {
          makeSelect.innerHTML += `<option value="${make}">${make} (${count})</option>`;
        }
      } catch (err) {
        console.error('Failed to load stats:', err);
      }
    }

    async function loadMeters() {
      try {
        const res = await fetch('/meters/query?page_size=500');
        const data = await res.json();
        allMeters = data.data;
        renderTable(allMeters);
        plotMap(allMeters);
      } catch (err) {
        console.error('Failed to load meters:', err);
      }
    }

    async function loadHierarchy() {
      try {
        const res = await fetch('/network');
        const data = await res.json();
        renderHierarchyTree(data.zones);
      } catch (err) {
        console.error('Failed to load hierarchy:', err);
      }
    }

    function renderHierarchyTree(zones) {
      const container = document.getElementById('hierarchyTree');
      if (!zones || zones.length === 0) {
        container.innerHTML = '<div style="color:var(--text-dim)">No hierarchy data found</div>';
        return;
      }

      let html = '';
      for (const zone of zones) {
        html += `<div style="font-weight:700; color:var(--accent-blue);">&#x1F3DB;&#xFE0F; ${zone.name} (${zone.code})</div>`;
        for (const circle of (zone.circles || [])) {
          html += `<div class="tree-node"><span class="tree-label">&#x25CB; Circle: ${circle.name}</span>`;
          for (const div of (circle.divisions || [])) {
            html += `<div class="tree-node"><span class="tree-label">&#x25CB; Division: ${div.name}</span>`;
            for (const sub of (div.subdivisions || [])) {
              html += `<div class="tree-node"><span class="tree-label">&#x25CB; Subdiv: ${sub.name}</span>`;
              for (const ss of (sub.substations || [])) {
                html += `<div class="tree-node"><span class="tree-label" style="color:var(--accent-amber);">&#x26A1; Substation: ${ss.name}</span>`;
                for (const feeder of (ss.feeders || [])) {
                  html += `<div class="tree-node"><span class="tree-label">&#x27A4; Feeder: ${feeder.name}</span>`;
                  for (const dt of (feeder.dts || [])) {
                    html += `<div class="tree-node"><span class="tree-label" style="color:var(--accent-green);">&#x1F50C; DT: ${dt.name} (${dt.meter_count} meters)</span></div>`;
                  }
                  html += `</div>`;
                }
                html += `</div>`;
              }
              html += `</div>`;
            }
            html += `</div>`;
          }
          html += `</div>`;
        }
      }
      container.innerHTML = html;
    }

    function plotMap(meters) {
      if (!markersLayer) return;
      markersLayer.clearLayers();
      const bounds = [];

      for (const m of meters) {
        if (!m.geo || !m.geo.lat) continue;
        const lat = m.geo.lat;
        const lng = m.geo.lng;
        bounds.push([lat, lng]);

        const color = m.installStatus === 'Decommissioned' ? '#f43f5e' : (m.phaseType === 'three' ? '#f59e0b' : '#38bdf8');
        const marker = L.circleMarker([lat, lng], {
          radius: 6,
          fillColor: color,
          color: '#fff',
          weight: 1,
          opacity: 0.9,
          fillOpacity: 0.8
        });

        marker.bindPopup(`
          <div style="font-family: 'Inter', sans-serif; color: #111;">
            <strong>${m.meterId}</strong> (${m.serialNo})<br>
            Make: <b>${m.make}</b> | Phase: <b>${m.phaseType}</b><br>
            Status: <b>${m.installStatus}</b><br>
            DT: <b>${m.dtCode}</b><br><br>
            <button onclick="openMeterDetail('${m.meterId}')" style="background:#2563eb;color:#fff;border:none;padding:5px 10px;border-radius:4px;cursor:pointer;font-size:12px;">View Consumption</button>
          </div>
        `);
        markersLayer.addLayer(marker);
      }

      if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [20, 20] });
        document.getElementById('mapStatus').innerText = `${bounds.length} meters plotted`;
      } else {
        document.getElementById('mapStatus').innerText = `No coordinates available`;
      }
    }

    function renderTable(meters) {
      const tbody = document.getElementById('metersTableBody');
      document.getElementById('tableCount').innerText = `Showing ${meters.length} meters`;

      if (meters.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding: 24px; color: var(--text-dim);">No matching meters found.</td></tr>';
        return;
      }

      tbody.innerHTML = meters.slice(0, 50).map(m => `
        <tr onclick="openMeterDetail('${m.meter_id}')">
          <td style="font-weight: 700; color: var(--accent-blue); font-family: 'JetBrains Mono', monospace;">${m.meter_id}</td>
          <td style="font-family: 'JetBrains Mono', monospace;">${m.serial_no}</td>
          <td>${m.make}</td>
          <td><span class="badge ${m.phase_type === 'three' ? 'badge-phase-3' : 'badge-phase-1'}">${m.phase_type}</span></td>
          <td><span class="badge ${m.install_status === 'Decommissioned' ? 'badge-decom' : 'badge-active'}">${m.install_status}</span></td>
          <td>${m.dt_code}</td>
          <td><button onclick="event.stopPropagation(); openMeterDetail('${m.meter_id}')" style="background:var(--bg-surface-elevated); border:1px solid var(--border-subtle); color:var(--text-main); padding:4px 8px; border-radius:4px; cursor:pointer;">Inspect</button></td>
        </tr>
      `).join('');
    }

    function debounceFilter() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(applyFilters, 250);
    }

    async function applyFilters() {
      const q = document.getElementById('filterQ').value;
      const make = document.getElementById('filterMake').value;
      const phase = document.getElementById('filterPhase').value;
      const status = document.getElementById('filterStatus').value;

      const params = new URLSearchParams({ page_size: '500' });
      if (q) params.set('q', q);
      if (make) params.set('make', make);
      if (phase) params.set('phase_type', phase);
      if (status) params.set('install_status', status);

      try {
        const res = await fetch('/meters/query?' + params.toString());
        const data = await res.json();
        renderTable(data.data);
      } catch (err) {
        console.error('Filter error:', err);
      }
    }

    async function openMeterDetail(meterId) {
      document.getElementById('meterModal').classList.add('open');
      document.getElementById('modalMeterId').innerText = `Meter: ${meterId}`;
      document.getElementById('modalDetails').innerHTML = '<div>Loading details...</div>';

      try {
        const [detailRes, energyRes] = await Promise.all([
          fetch(`/meters/${meterId}`),
          fetch(`/meters/${meterId}/energy`)
        ]);

        const detail = await detailRes.json();
        const energy = await energyRes.json();

        // Render nameplate & hierarchy
        const np = detail.nameplate || {};
        const h = detail.hierarchy || {};
        const geo = detail.geo || {};

        document.getElementById('modalDetails').innerHTML = `
          <div class="detail-item"><div class="detail-label">Serial Number</div><div class="detail-value">${np.serial_no || '--'}</div></div>
          <div class="detail-item"><div class="detail-label">Make & Model</div><div class="detail-value">${np.make || '--'}</div></div>
          <div class="detail-item"><div class="detail-label">Phase Type</div><div class="detail-value">${np.phase_type || '--'}</div></div>
          <div class="detail-item"><div class="detail-label">Status</div><div class="detail-value">${np.install_status || '--'}</div></div>
          <div class="detail-item"><div class="detail-label">Feeder</div><div class="detail-value">${h.feeder ? h.feeder.name : '--'}</div></div>
          <div class="detail-item"><div class="detail-label">Distribution Transformer</div><div class="detail-value">${h.dt ? h.dt.name : '--'}</div></div>
          <div class="detail-item"><div class="detail-label">GPS Coordinates</div><div class="detail-value">${geo.latitude ? geo.latitude.toFixed(4) + ', ' + geo.longitude.toFixed(4) : '--'}</div></div>
          <div class="detail-item"><div class="detail-label">Total Readings</div><div class="detail-value">${Array.isArray(energy) ? energy.length : 0}</div></div>
        `;

        // Render Chart
        renderConsumptionChart(energy);
      } catch (err) {
        console.error('Detail load error:', err);
      }
    }

    function renderConsumptionChart(readings) {
      const ctx = document.getElementById('consumptionChart').getContext('2d');
      if (chartInstance) chartInstance.destroy();

      if (!readings || readings.length === 0) {
        return;
      }

      // Read last 40 readings for clean timeline
      const sample = readings.slice(-40);
      const labels = sample.map(r => r.timestamp.split(' ')[1] || r.timestamp);
      const kwhData = sample.map(r => parseFloat(r.kwh) || 0);
      const voltData = sample.map(r => parseFloat(r.volt_r) || 0);

      chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Cumulative Energy (kWh)',
              data: kwhData,
              borderColor: '#38bdf8',
              backgroundColor: 'rgba(56, 189, 248, 0.1)',
              yAxisID: 'yKwh',
              tension: 0.3,
              fill: true
            },
            {
              label: 'R-Phase Voltage (V)',
              data: voltData,
              borderColor: '#f59e0b',
              borderDash: [4, 4],
              yAxisID: 'yVolt',
              tension: 0.2
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            yKwh: {
              type: 'linear',
              position: 'left',
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { color: '#94a3b8' }
            },
            yVolt: {
              type: 'linear',
              position: 'right',
              grid: { drawOnChartArea: false },
              ticks: { color: '#f59e0b' }
            },
            x: {
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { color: '#94a3b8' }
            }
          },
          plugins: {
            legend: { labels: { color: '#f1f5f9' } }
          }
        }
      });
    }

    function closeModal() {
      document.getElementById('meterModal').classList.remove('open');
    }

    async function syncData() {
      const btn = document.getElementById('syncBtn');
      btn.innerText = 'Syncing...';
      btn.disabled = true;
      try {
        await fetch('/sync', { method: 'POST' });
        await Promise.all([loadStats(), loadMeters(), loadHierarchy()]);
      } catch (err) {
        alert('Sync error: ' + err);
      } finally {
        btn.innerText = '↺ Sync Live Portal';
        btn.disabled = false;
      }
    }

    // Bootstrap
    window.onload = () => {
      initMap();
      loadStats();
      loadMeters();
      loadHierarchy();
    };
  </script>
</body>
</html>
"""
