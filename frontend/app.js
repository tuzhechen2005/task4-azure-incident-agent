"use strict";

(function (globalScope) {
  const severityLabels = Object.freeze({
    "SEV-1": "SEV-1 Critical",
    "SEV-2": "SEV-2 High",
    "SEV-3": "SEV-3 Medium",
    "SEV-4": "SEV-4 Low",
  });

  const byId = (id) => globalScope.document.getElementById(id);
  const setText = (id, value, fallback = "—") => {
    byId(id).textContent = value === null || value === undefined || value === "" ? fallback : String(value);
  };
  const setHidden = (id, hidden) => { byId(id).hidden = hidden; };

  function createInitialState() {
    return {
      health: null,
      stats: null,
      incidents: [],
      selected: null,
      filters: { severity: "", status: "", service: "", region: "" },
      view: "loading",
      stale: false,
      error: null,
    };
  }

  function createPollController({
    fetchJson,
    intervalMs,
    onSuccess,
    onError,
    setIntervalFn = globalScope.setInterval.bind(globalScope),
    clearIntervalFn = globalScope.clearInterval.bind(globalScope),
  }) {
    let refreshing = false;
    let timer = null;

    async function refresh() {
      if (refreshing) return false;
      refreshing = true;
      try {
        const [health, stats, listing] = await Promise.all([
          fetchJson("/api/health"),
          fetchJson("/api/stats"),
          fetchJson("/api/incidents?page=1&page_size=100"),
        ]);
        onSuccess({ health, stats, incidents: listing.items || [] });
        return true;
      } catch (error) {
        onError(error);
        return false;
      } finally {
        refreshing = false;
      }
    }

    async function start() {
      if (timer === null) timer = setIntervalFn(() => refresh(), intervalMs);
      return refresh();
    }

    function stop() {
      if (timer !== null) clearIntervalFn(timer);
      timer = null;
    }

    return Object.freeze({ start, stop, refresh, isRefreshing: () => refreshing });
  }

  const state = createInitialState();

  function formatLocalTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? "Invalid time" : date.toLocaleString();
  }

  function severityLabel(value) {
    return severityLabels[value] || `${value || "UNKNOWN"} Unclassified`;
  }

  function transformIncidents(records, filters) {
    const service = filters.service.trim().toLocaleLowerCase();
    const region = filters.region.trim().toLocaleLowerCase();
    return records.filter((record) => {
      const incident = record.incident;
      const analysis = record.analysis;
      return (!filters.severity || analysis.severity === filters.severity)
        && (!filters.status || incident.status === filters.status)
        && (!service || incident.services.some((item) => item.toLocaleLowerCase().includes(service)))
        && (!region || incident.regions.some((item) => item.toLocaleLowerCase().includes(region)));
    });
  }

  function renderHealth(health) {
    const status = health ? health.status : "unknown";
    setText("healthBadge", status === "healthy" ? "Healthy" : status === "degraded" ? "Degraded" : "Unknown");
    byId("healthBadge").dataset.status = status;
    setText("analysisMode", health && health.analysis_mode);
    setText("lastSuccess", formatLocalTime(health && health.last_successful_ingestion_at));
  }

  function renderStats(stats) {
    const severity = (stats && stats.severity_counts) || {};
    const statuses = (stats && stats.status_counts) || {};
    setText("totalCount", stats ? stats.total : 0, "0");
    setText("sev1Count", severity["SEV-1"] || 0, "0");
    setText("sev2Count", severity["SEV-2"] || 0, "0");
    setText("sev3Count", severity["SEV-3"] || 0, "0");
    setText("sev4Count", severity["SEV-4"] || 0, "0");
    setText("activeCount", statuses.ACTIVE || 0, "0");
    setText("resolvedCount", statuses.RESOLVED || 0, "0");
  }

  function createCell(text, className = "") {
    const cell = globalScope.document.createElement("td");
    if (className) cell.className = className;
    cell.textContent = text;
    return cell;
  }

  function renderIncidents(records) {
    const visible = transformIncidents(records, state.filters);
    const rows = visible.map((record) => {
      const row = globalScope.document.createElement("tr");
      const incident = record.incident;
      const analysis = record.analysis;
      row.append(createCell(formatLocalTime(incident.updated_at)));
      const titleCell = globalScope.document.createElement("td");
      const button = globalScope.document.createElement("button");
      button.type = "button";
      button.className = "incident-button";
      button.textContent = incident.title;
      button.addEventListener("click", () => selectRecord(record));
      titleCell.append(button);
      row.append(titleCell);
      row.append(createCell(`${incident.services.join(", ") || "Unknown service"} · ${incident.regions.join(", ") || "Unknown region"}`, "muted"));
      row.append(createCell(incident.status));
      row.append(createCell(severityLabel(analysis.severity)));
      row.append(createCell(analysis.summary));
      return row;
    });
    byId("incidentRows").replaceChildren(...rows);
    setText("resultCount", `${visible.length} result${visible.length === 1 ? "" : "s"}`);
    setHidden("emptyState", state.view === "loading" || visible.length > 0);
  }

  function renderList(id, values, emptyText = "None provided") {
    const list = byId(id);
    const source = values && values.length ? values : [emptyText];
    const items = source.map((value) => {
      const item = globalScope.document.createElement("li");
      item.textContent = value;
      return item;
    });
    list.replaceChildren(...items);
  }

  function renderDetail(record) {
    if (!record) return;
    const incident = record.incident;
    const analysis = record.analysis;
    const responsePlan = analysis.response_plan || {};
    setText("detailSeverity", severityLabel(analysis.severity));
    setText("detailTitle", incident.title);
    setText("detailStatus", incident.status);
    setText("detailServices", incident.services.join(", "), "Unknown");
    setText("detailRegions", incident.regions.join(", "), "Unknown");
    setText("detailPublished", formatLocalTime(incident.published_at));
    setText("detailUpdated", formatLocalTime(incident.updated_at));
    setText("detailSource", analysis.analysis_source);
    setText("detailConfidence", `${Math.round(analysis.confidence * 100)}%`);
    setText("detailSummary", analysis.summary);
    setText("detailScope", analysis.scope);
    setText("detailRationale", analysis.rationale);
    byId("sourceLink").href = incident.source_link || incident.source_url;
    renderList("detailImpact", analysis.potential_impact);
    renderList("detailActions", analysis.recommended_actions);
    renderList("planImmediate", responsePlan.immediate_actions);
    renderList("planInvestigation", responsePlan.investigation_steps);
    renderList("planMitigation", responsePlan.mitigation_options);
    renderList("planCommunication", responsePlan.communication_plan);
    renderList("planRecovery", responsePlan.recovery_checks);
    renderList("planEscalation", responsePlan.escalation_conditions);
    renderList("detailWarnings", analysis.warnings, "No warnings");
  }

  async function fetchJson(path) {
    const response = await globalScope.fetch(path, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`API request failed with status ${response.status}`);
    return response.json();
  }

  function selectRecord(record) {
    state.selected = record;
    state.view = "selected";
    renderDetail(record);
    renderStates();
    fetchJson(`/api/incidents/${encodeURIComponent(record.incident.incident_id)}`)
      .then((detail) => {
        state.selected = detail;
        renderDetail(detail);
      })
      .catch(() => {
        state.stale = true;
        renderStates();
      });
  }

  function renderStates() {
    setHidden("loadingState", state.view !== "loading");
    setHidden("errorState", state.view !== "error");
    setHidden("staleState", !state.stale);
    setHidden("noSelectionState", Boolean(state.selected));
    setHidden("selectedState", !state.selected);
    if (state.error) setText("errorMessage", state.error);
    const labels = { loading: "Loading", empty: "No incidents", error: "Refresh failed", stale: "Showing stale data", selected: "Incident selected", "no-selection": "No incident selected" };
    setText("statusAnnouncer", labels[state.view] || "Dashboard ready", "");
  }

  function renderDashboard() {
    renderHealth(state.health);
    renderStats(state.stats);
    renderIncidents(state.incidents);
    if (state.selected) renderDetail(state.selected);
    renderStates();
  }

  function applyRefreshSuccess(payload) {
    const selectedId = state.selected && state.selected.incident.incident_id;
    state.health = payload.health;
    state.stats = payload.stats;
    state.incidents = payload.incidents;
    state.selected = selectedId
      ? payload.incidents.find((record) => record.incident.incident_id === selectedId) || state.selected
      : null;
    state.view = state.selected ? "selected" : state.incidents.length ? "no-selection" : "empty";
    state.stale = false;
    state.error = null;
    renderDashboard();
  }

  function applyRefreshError() {
    state.error = "Unable to refresh the dashboard API. Prior data is retained.";
    state.stale = Boolean(state.health || state.stats || state.incidents.length);
    state.view = "error";
    renderDashboard();
  }

  function readFilters() {
    state.filters = {
      severity: byId("severityFilter").value,
      status: byId("statusFilter").value,
      service: byId("serviceFilter").value,
      region: byId("regionFilter").value,
    };
    renderIncidents(state.incidents);
  }

  function clearFilters() {
    byId("filterForm").reset();
    readFilters();
  }

  const publicApi = Object.freeze({
    createInitialState,
    createPollController,
    formatLocalTime,
    severityLabel,
    transformIncidents,
    renderDashboard,
    state,
  });

  let pollController = null;

  function bootstrap() {
    byId("filterForm").addEventListener("input", readFilters);
    byId("clearFiltersButton").addEventListener("click", clearFilters);
    byId("refreshButton").addEventListener("click", () => pollController.refresh());
    byId("retryButton").addEventListener("click", () => pollController.refresh());
    renderDashboard();
    pollController.start();
  }

  if (globalScope.document) {
    const configured = Number(globalScope.document.querySelector('meta[name="dashboard-poll-seconds"]')?.content);
    const intervalSeconds = Number.isFinite(configured) && configured > 0 ? configured : 30;
    pollController = createPollController({
      fetchJson,
      intervalMs: intervalSeconds * 1000,
      onSuccess: applyRefreshSuccess,
      onError: applyRefreshError,
    });
    globalScope.AzureDashboard = publicApi;
    globalScope.document.addEventListener("DOMContentLoaded", bootstrap);
    globalScope.addEventListener("beforeunload", () => pollController.stop(), { once: true });
  }

  if (typeof module !== "undefined" && module.exports) module.exports = publicApi;
}(typeof window !== "undefined" ? window : globalThis));
