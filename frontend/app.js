"use strict";

(function () {
  const severityLabels = Object.freeze({
    "SEV-1": "SEV-1 Critical",
    "SEV-2": "SEV-2 High",
    "SEV-3": "SEV-3 Medium",
    "SEV-4": "SEV-4 Low",
  });

  const byId = (id) => document.getElementById(id);
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
    const cell = document.createElement("td");
    if (className) cell.className = className;
    cell.textContent = text;
    return cell;
  }

  function renderIncidents(records) {
    const visible = transformIncidents(records, state.filters);
    const rows = visible.map((record) => {
      const row = document.createElement("tr");
      const incident = record.incident;
      const analysis = record.analysis;
      row.append(createCell(formatLocalTime(incident.updated_at)));
      const titleCell = document.createElement("td");
      const button = document.createElement("button");
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
      const item = document.createElement("li");
      item.textContent = value;
      return item;
    });
    list.replaceChildren(...items);
  }

  function selectRecord(record) {
    state.selected = record;
    state.view = "selected";
    renderDetail(record);
    renderStates();
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
    const sourceLink = byId("sourceLink");
    sourceLink.href = incident.source_link || incident.source_url;
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

  function renderStates() {
    setHidden("loadingState", state.view !== "loading");
    setHidden("errorState", state.view !== "error");
    setHidden("staleState", !state.stale);
    setHidden("noSelectionState", state.view === "selected");
    setHidden("selectedState", state.view !== "selected");
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

  function bootstrap() {
    byId("filterForm").addEventListener("input", readFilters);
    byId("clearFiltersButton").addEventListener("click", clearFilters);
    byId("refreshButton").addEventListener("click", () => window.dispatchEvent(new Event("dashboard:refresh")));
    byId("retryButton").addEventListener("click", () => window.dispatchEvent(new Event("dashboard:refresh")));
    renderDashboard();
  }

  window.AzureDashboard = Object.freeze({ createInitialState, formatLocalTime, severityLabel, transformIncidents, renderDashboard, state });
  document.addEventListener("DOMContentLoaded", bootstrap);
}());
