# Development Tasks

## Working Agreement

- Follow `AGENTS.md` and the contracts in `SPEC.md`.
- Implement exactly one task at a time using Red–Green–Refactor; never work on tasks concurrently.
- Status values: `TODO`, `IN PROGRESS`, `BLOCKED`, `DONE`.
- Do not start implementation until the human approves `SPEC.md` and this task plan.
- If a specification change is approved, update affected tasks before implementation.
- During an active Goal, each completed task is a checkpoint rather than a stopping point: after all checks pass, mark it `DONE`, create its dedicated Conventional Commit, and immediately continue with the next eligible task.
- Pause only for a genuine blocker, specification conflict, destructive action, missing authority, or material decision that requires human input.
- The Goal is complete only when every task in its declared scope is `DONE` and the complete validation suite passes.

## Recommended Order

`TASK-001 → TASK-002 → TASK-003 → TASK-004 → TASK-005 → TASK-006 → TASK-007 → TASK-008 → TASK-009 → TASK-010 → TASK-011 → TASK-012 → TASK-013 → TASK-014 → TASK-015 → TASK-016`

---

## TASK-001 — Project Skeleton and Configuration

**Status:** DONE

**Goal:** Create the minimal Python project skeleton, dependency manifest, safe configuration model, logging setup, and test runner foundation.

**Files:** `requirements.txt`, `.env.example`, `.gitignore`, `app/__init__.py`, `app/config.py`, `app/logging_config.py`, `tests/conftest.py`, configuration tests, and `README.md` (required to document the default offline test command).

**Dependencies:** None; specification approval required.

**Implementation Requirements:**

- Support every variable in SPEC Section 13 with typed validation and safe defaults.
- Reject non-positive timeouts/intervals, negative retries, and invalid database paths cleanly.
- Ensure `.env`, databases, caches, and generated reports are ignored.
- Configure structured, readable logging without secrets.
- Establish one documented offline default test command.

**Acceptance Criteria:**

- Settings load from defaults and environment overrides.
- Invalid settings fail with actionable messages.
- Secrets are absent from defaults and log output.
- Test discovery works in a clean environment.

**Tests Required:** `test_settings_defaults`, `test_settings_environment_override`, `test_settings_reject_invalid_intervals`, `test_settings_missing_llm_key_enables_fallback_mode`, `test_logging_redacts_secret_values`.

---

## TASK-002 — Domain Schemas and Validation

**Status:** DONE

**Goal:** Define all validated enums and data contracts from SPEC Section 6.

**Files:** `app/models/__init__.py`, `app/models/schemas.py`, `tests/unit/test_schemas.py`.

**Dependencies:** TASK-001.

**Implementation Requirements:**

- Implement `RawIncident`, `NormalizedIncident`, `AgentInput`, `IncidentAnalysis`, `ResponsePlan`, `IncidentRecord`, list/stats/cycle/error schemas, and required enums.
- Enforce UTC-aware timestamps, nonblank required text, confidence range, URL validation, list defaults, and incident-ID consistency.
- Support stable JSON serialization/deserialization.

**Acceptance Criteria:**

- Valid examples round-trip without data loss.
- Missing or invalid required fields fail validation.
- Mutable defaults are not shared.
- Enum and datetime JSON values match SPEC.

**Tests Required:** `test_raw_incident_valid`, `test_normalized_incident_requires_utc_times`, `test_analysis_accepts_each_severity`, `test_analysis_rejects_invalid_confidence`, `test_analysis_incident_id_consistency`, `test_response_plan_defaults_are_isolated`, `test_schema_json_round_trip`, `test_missing_required_field`.

---

## TASK-003 — RSS HTTP Client

**Status:** DONE

**Goal:** Retrieve a configured feed reliably and map external failures into controlled application errors.

**Files:** `app/ingestion/__init__.py`, `app/ingestion/rss_client.py`, `tests/unit/test_rss_client.py`.

**Dependencies:** TASK-001.

**Implementation Requirements:**

- Use injected/configured HTTP transport, timeout, user agent, and bounded retries.
- Return bytes plus retrieval metadata needed by the parser.
- Distinguish timeout, network, HTTP status, and empty-body failures.
- Never log credentials or uncontrolled full response bodies.

**Acceptance Criteria:**

- A successful mocked response returns exact feed bytes and fetch metadata.
- Retry behavior is bounded and deterministic.
- All defined external failures become typed/controlled errors.
- Unit tests make no network connection.

**Tests Required:** `test_fetch_valid_feed`, `test_fetch_timeout`, `test_fetch_network_error`, `test_fetch_http_error`, `test_fetch_empty_body`, `test_fetch_retries_within_limit`, `test_fetch_does_not_retry_nonretryable_error`.

---

## TASK-004 — Feed Parser

**Status:** DONE

**Goal:** Parse RSS/Atom content into `RawIncident` objects while isolating malformed entries.

**Files:** `app/ingestion/parser.py`, `tests/fixtures/rss_valid.xml`, `tests/fixtures/rss_empty.xml`, `tests/fixtures/rss_malformed_entry.xml`, `tests/unit/test_parser.py`.

**Dependencies:** TASK-002, TASK-003.

**Implementation Requirements:**

- Parse RSS/Atom-compatible entries from supplied bytes only.
- Extract source ID, title, description as plain text, link, and publication time.
- Report feed-level failure separately from entry-level warnings.
- Skip a malformed entry and continue valid siblings.

**Acceptance Criteria:**

- Valid fixture entries map to exact `RawIncident` fields.
- Empty valid feed returns an empty list without error.
- Invalid XML returns a controlled parse error.
- Unsafe HTML is not preserved as executable markup.

**Tests Required:** `test_parse_valid_feed`, `test_parse_atom_variant`, `test_parse_empty_feed`, `test_parse_invalid_xml`, `test_parse_skips_malformed_entry`, `test_parse_missing_optional_fields`, `test_parse_description_as_plain_text`, `test_parse_timezone_to_utc`.

---

## TASK-005 — Incident Normalization and Identity

**Status:** DONE

**Goal:** Convert raw feed entries into stable, validated normalized incidents.

**Files:** `app/ingestion/normalizer.py`, `tests/unit/test_normalizer.py`.

**Dependencies:** TASK-002, TASK-004.

**Implementation Requirements:**

- Normalize whitespace, timestamps, status keywords, service names, and regions conservatively.
- Prefer source event ID for identity; otherwise use deterministic fallback identity.
- Produce a separate material-content fingerprint for change detection.
- Do not invent service/region values when text has insufficient evidence.

**Acceptance Criteria:**

- Same source event always yields the same incident ID.
- Same identity with changed material text yields a changed fingerprint.
- Missing optional source fields still yield a valid incident where possible.
- Status mapping supports active, monitoring, resolved, and unknown examples.

**Tests Required:** `test_normalize_complete_incident`, `test_normalize_missing_service_region`, `test_identity_prefers_source_event_id`, `test_identity_fallback_is_deterministic`, `test_content_change_changes_fingerprint_not_identity`, `test_status_mapping`, `test_invalid_required_text`, `test_normalize_utc_timestamps`.

---

## TASK-006 — SQLite Database and Repository

**Status:** DONE

**Goal:** Persist, retrieve, filter, paginate, and atomically update incident records and analyses.

**Files:** `app/storage/__init__.py`, `app/storage/database.py`, `app/storage/repository.py`, `tests/unit/test_repository.py`.

**Dependencies:** TASK-001, TASK-002.

**Implementation Requirements:**

- Initialize the SQLite schema safely and enforce unique incident IDs.
- Store validated incident and analysis data with atomic transactions.
- Provide lookup, create/update, paginated/filterable list, and stats operations.
- Validate JSON fields on repository boundaries and use temporary databases in tests.

**Acceptance Criteria:**

- Data survives repository close/reopen.
- Duplicate inserts do not create duplicate rows.
- Failed incident-plus-analysis writes roll back fully.
- Filters, ordering, pagination totals, not-found behavior, and stats are correct.

**Tests Required:** `test_initialize_database`, `test_insert_and_get_record`, `test_persistence_after_reopen`, `test_unique_incident_id`, `test_atomic_upsert_rollback`, `test_update_changed_record`, `test_list_empty`, `test_list_filters_and_order`, `test_pagination_total`, `test_stats_counts`, `test_get_missing_incident`.

---

## TASK-007 — LLM Client Interface and Prompt Templates

**Status:** DONE

**Goal:** Define a provider-neutral LLM boundary and prompts that demand the Decision Agent schema.

**Files:** `app/agents/__init__.py`, `app/agents/client.py`, `app/agents/prompts.py`, `tests/unit/test_prompts.py`, `tests/unit/test_llm_client.py`.

**Dependencies:** TASK-001, TASK-002.

**Implementation Requirements:**

- Define an injectable `LLMClient` protocol and typed error categories.
- Build the system prompt and user template from validated `AgentInput`.
- Include severity rubric, strict JSON instruction, non-invention policy, and prompt-injection boundary.
- Keep provider credentials and SDK calls outside prompt construction.

**Acceptance Criteria:**

- Prompt construction is deterministic for fixed input.
- The prompt contains all schema-required fields and severity definitions.
- Feed text is clearly delimited and treated as untrusted data.
- Fake clients can be used without provider SDK or network access.

**Tests Required:** `test_prompt_contains_severity_rubric`, `test_prompt_contains_output_contract`, `test_prompt_delimits_untrusted_incident_text`, `test_prompt_does_not_interpolate_secrets`, `test_fake_llm_client_contract`, `test_llm_error_categories`.

---

## TASK-008 — Decision Agent, Validation, and Fallback

**Status:** TODO

**Goal:** Produce validated incident analyses from the LLM client and remain functional on every specified LLM failure.

**Files:** `app/agents/decision_agent.py`, `tests/unit/test_decision_agent.py`.

**Dependencies:** TASK-002, TASK-007.

**Implementation Requirements:**

- Call the injected client, parse strict JSON, validate schema and incident-ID match, and label source/model.
- Permit at most the configured repair/retry behavior.
- Implement deterministic conservative fallback from SPEC Section 7.3.
- Never return unvalidated partial model output.

**Acceptance Criteria:**

- Valid model output returns `analysis_source=LLM`.
- Each severity can be accepted when its structure is valid.
- Invalid JSON, missing fields, wrong ID, timeout, provider error, and exhausted repair return a valid fallback.
- Resolved/informational fallback is `SEV-4`; uncertain active fallback is `SEV-3` with low confidence and warnings.

**Tests Required:** `test_valid_llm_analysis`, `test_accepts_sev1`, `test_accepts_sev2`, `test_accepts_sev3`, `test_accepts_sev4`, `test_invalid_json_uses_fallback`, `test_missing_field_uses_fallback`, `test_wrong_incident_id_uses_fallback`, `test_timeout_uses_fallback`, `test_provider_error_uses_fallback`, `test_single_repair_attempt`, `test_fallback_active_severity`, `test_fallback_resolved_severity`, `test_fallback_is_deterministic`.

---

## TASK-009 — Incident Processing Service

**Status:** TODO

**Goal:** Orchestrate parse/normalize, deduplication, conditional analysis, atomic persistence, and per-cycle reporting.

**Files:** `app/services/__init__.py`, `app/services/incident_service.py`, `tests/unit/test_incident_service.py`.

**Dependencies:** TASK-004, TASK-005, TASK-006, TASK-008.

**Implementation Requirements:**

- Process all valid entries independently and return cycle counts/errors.
- Analyze and insert new incidents.
- Skip LLM calls for unchanged fingerprints.
- Re-analyze and update changed incidents atomically.
- Preserve prior records when fetching/parsing fails.

**Acceptance Criteria:**

- Cycle counts match actual new, changed, unchanged, and failed entries.
- One entry failure does not prevent valid sibling processing.
- Unchanged duplicates make zero additional LLM calls.
- Changed records replace their latest analysis without duplicating identity.

**Tests Required:** `test_process_new_incident`, `test_process_multiple_incidents`, `test_unchanged_incident_skips_agent`, `test_changed_incident_reanalyzes`, `test_entry_failure_does_not_abort_cycle`, `test_fetch_failure_preserves_storage`, `test_empty_feed_cycle`, `test_cycle_result_counts`, `test_atomic_service_update`.

---

## TASK-010 — Scheduler and Lifecycle

**Status:** TODO

**Goal:** Run ingestion on startup and at the configured interval with overlap protection and graceful shutdown.

**Files:** `app/scheduler.py`, `tests/unit/test_scheduler.py`.

**Dependencies:** TASK-001, TASK-009.

**Implementation Requirements:**

- Inject the clock/scheduling boundary where needed for deterministic tests.
- Run once at startup, then at the configured interval.
- Prevent concurrent cycles in one process and expose safe last-run state.
- Catch cycle exceptions and keep future scheduling alive.
- Stop cleanly on application shutdown.

**Acceptance Criteria:**

- Tests can advance time without sleeping or using a network.
- Startup, repeated run, overlap skip, exception recovery, and shutdown work as specified.
- Last run and last successful run timestamps are available to health/stats layers.

**Tests Required:** `test_runs_once_on_startup`, `test_runs_at_configured_interval`, `test_prevents_overlapping_cycles`, `test_cycle_exception_does_not_stop_scheduler`, `test_records_last_success`, `test_graceful_shutdown`.

---

## TASK-011 — FastAPI Application and Error Handling

**Status:** TODO

**Goal:** Create the application factory, lifecycle wiring, request IDs, static serving boundary, and standard error responses.

**Files:** `app/api/__init__.py`, `app/api/app.py`, `app/api/errors.py`, `tests/integration/test_app.py`, `main.py`.

**Dependencies:** TASK-006, TASK-009, TASK-010.

**Implementation Requirements:**

- Use an application factory with injectable dependencies for tests.
- Initialize database/scheduler on startup and stop scheduler on shutdown.
- Map controlled application errors to safe HTTP responses and attach request IDs.
- Prepare static dashboard serving without implementing dashboard content in this task.

**Acceptance Criteria:**

- Test app starts and shuts down without a live feed or LLM.
- Dependency failures return safe errors without stack traces or secrets.
- Static path is wired and API paths are not shadowed.
- `main.py` provides the documented local entry point.

**Tests Required:** `test_app_startup_and_shutdown`, `test_app_uses_injected_dependencies`, `test_request_id_present_on_error`, `test_unhandled_error_is_sanitized`, `test_static_mount_does_not_shadow_api`.

---

## TASK-012 — Health and Statistics APIs

**Status:** TODO

**Goal:** Implement `/api/health` and `/api/stats` exactly as specified.

**Files:** `app/api/routes.py`, `tests/integration/test_health_stats_api.py`.

**Dependencies:** TASK-006, TASK-010, TASK-011.

**Implementation Requirements:**

- Report database, scheduler, analysis mode, last ingestion, last success, and safe last-error summary.
- Treat RSS/LLM fallback as degraded `200`; use `503` only when persisted data cannot be served.
- Return stats derived from repository state, including valid empty values.

**Acceptance Criteria:**

- Response bodies validate against health/stats contracts.
- Healthy, degraded, and unavailable database states use correct status codes.
- Stats counts match seeded repository records.

**Tests Required:** `test_health_healthy`, `test_health_degraded_rss`, `test_health_fallback_analysis_mode`, `test_health_database_unavailable`, `test_stats_empty`, `test_stats_seeded_counts`, `test_stats_latest_timestamps`, `test_health_response_schema`.

---

## TASK-013 — Incident List and Detail APIs

**Status:** TODO

**Goal:** Implement paginated/filterable incident listing and incident detail endpoints.

**Files:** `app/api/routes.py`, `tests/integration/test_incidents_api.py`.

**Dependencies:** TASK-006, TASK-011.

**Implementation Requirements:**

- Implement the query parameters, maximum page size, ordering, and response envelopes in SPEC Section 10.
- Validate severity/status enums and positive pagination values.
- Return standard `INCIDENT_NOT_FOUND` response for unknown IDs.

**Acceptance Criteria:**

- Empty and populated list responses have correct schemas and totals.
- Severity, status, service, and region filters work alone and in combination.
- Pagination is deterministic and capped.
- Detail returns the stored normalized incident and latest analysis.

**Tests Required:** `test_list_incidents_empty`, `test_list_incidents_default_order`, `test_list_incidents_pagination`, `test_list_incidents_filter_severity`, `test_list_incidents_filter_status`, `test_list_incidents_filter_service_region`, `test_list_incidents_invalid_query`, `test_get_incident`, `test_get_incident_not_found`, `test_incident_response_schema`.

---

## TASK-014 — Dashboard Structure and Rendering

**Status:** TODO

**Goal:** Build the accessible local dashboard and deterministic rendering/state logic.

**Files:** `frontend/index.html`, `frontend/styles.css`, `frontend/app.js`, `tests/frontend/test_dashboard_static.py`, optional JavaScript unit-test setup only if kept lightweight.

**Dependencies:** TASK-012, TASK-013.

**Implementation Requirements:**

- Implement every component and state in SPEC Section 11.
- Separate API fetching/state transformation from DOM rendering functions.
- Render untrusted content with safe text APIs, never raw `innerHTML`.
- Include severity text labels, keyboard/focus support, responsive layout, and local-time formatting.

**Acceptance Criteria:**

- Fixture/mock data visibly maps to health, cards, list, filters, detail, actions, and all response-plan sections.
- Loading, empty, error, stale, selected, and no-selection states are representable.
- Page works without a frontend build step.
- Static checks confirm required semantics and safe rendering approach.

**Tests Required:** `test_dashboard_has_required_regions`, `test_dashboard_has_accessible_labels`, `test_dashboard_loads_local_assets`, `test_dashboard_does_not_render_dynamic_inner_html`, `test_severity_has_text_label`, and deterministic tests for filter/state transformation functions or a documented mock-data verification fixture.

---

## TASK-015 — Dashboard Polling and End-to-End Integration

**Status:** TODO

**Goal:** Connect the dashboard to APIs, verify periodic non-overlapping refresh, and exercise the complete local workflow with controlled dependencies.

**Files:** `frontend/app.js`, `tests/frontend/test_dashboard_polling.*`, `tests/integration/test_end_to_end.py`, integration fixtures.

**Dependencies:** TASK-009, TASK-010, TASK-012, TASK-013, TASK-014.

**Implementation Requirements:**

- Fetch health, stats, and incidents on load and at configured intervals; fetch detail on selection.
- Prevent overlapping refreshes, retain last good data on error, expose retry/stale state, and clean up timers.
- Test feed → normalization → mocked agent/fallback → SQLite → API with fixtures only.
- Verify restart persistence and unchanged-duplicate behavior end to end.

**Acceptance Criteria:**

- The dashboard refreshes without page reload and does not launch concurrent refreshes.
- A temporary API failure leaves prior data visible and recovery clears stale state.
- The controlled full pipeline produces API-visible records and statistics.
- Default integration tests remain offline and deterministic.

**Tests Required:** `test_poll_on_initial_load`, `test_poll_at_configured_interval`, `test_poll_prevents_overlap`, `test_poll_error_retains_last_data`, `test_poll_recovers`, `test_fixture_feed_to_api`, `test_fallback_feed_to_api`, `test_duplicate_end_to_end`, `test_restart_persistence`.

---

## TASK-016 — Documentation, Retrospective, and Delivery Audit

**Status:** TODO

**Goal:** Produce complete operator/developer documentation, project retrospective, and final acceptance/ZIP audit without changing product behavior.

**Files:** `README.md`, `docs/RETROSPECTIVE.md`, `.env.example`, `.gitignore`, `requirements.txt`, `SPEC.md` acceptance checklist, documentation validation tests/checklist.

**Dependencies:** TASK-001 through TASK-015.

**Implementation Requirements:**

- Document purpose, architecture, module responsibilities, data flow, schemas, configuration, install/run/test commands, offline demo, prompt strategy, polling, failures, directory structure, and troubleshooting.
- Retrospective must cover goals, decisions, SDD/TDD workflow, Decision Agent design, limitations, lessons, and improvements.
- Execute the full offline suite and manually verify final acceptance criteria.
- Audit the ZIP manifest and exclude `.env`, databases, caches, virtual environments, logs, and test/build artifacts.

**Acceptance Criteria:**

- A new developer can run the application and offline demo from README instructions.
- Every FR-020 topic and SPEC final acceptance item has documented evidence or an explicit `FAIL` with reason.
- Configuration reference matches actual settings.
- Delivery archive contains the required source and documents only.

**Tests Required:** Documentation-only RED is replaced by validation: run all default tests; execute documented setup/run/test commands in a clean environment where practical; check internal links and referenced paths; scan the delivery manifest for secrets and excluded artifacts; record `PASS/FAIL` for AC-001 through AC-018.

---

## Progress Summary

| Task | Title | Status |
|---|---|---|
| TASK-001 | Project Skeleton and Configuration | DONE |
| TASK-002 | Domain Schemas and Validation | DONE |
| TASK-003 | RSS HTTP Client | DONE |
| TASK-004 | Feed Parser | DONE |
| TASK-005 | Incident Normalization and Identity | DONE |
| TASK-006 | SQLite Database and Repository | DONE |
| TASK-007 | LLM Client Interface and Prompt Templates | DONE |
| TASK-008 | Decision Agent, Validation, and Fallback | TODO |
| TASK-009 | Incident Processing Service | TODO |
| TASK-010 | Scheduler and Lifecycle | TODO |
| TASK-011 | FastAPI Application and Error Handling | TODO |
| TASK-012 | Health and Statistics APIs | TODO |
| TASK-013 | Incident List and Detail APIs | TODO |
| TASK-014 | Dashboard Structure and Rendering | TODO |
| TASK-015 | Dashboard Polling and End-to-End Integration | TODO |
| TASK-016 | Documentation, Retrospective, and Delivery Audit | TODO |
