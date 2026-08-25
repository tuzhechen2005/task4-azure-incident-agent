# Project Retrospective

## Goal and outcome

The goal was to turn an approved specification and ordered task plan into a locally runnable Azure public-status incident response agent and monitoring dashboard. The result covers ingestion, defensive parsing, normalization, stable identity and change detection, validated analysis/fallback, atomic SQLite persistence, scheduling, four FastAPI endpoints, a responsive no-build dashboard, offline tests, operator documentation, and delivery evidence.

The project intentionally stays local and simple: one Python process, one SQLite database, standard HTML/CSS/JavaScript, no cloud account requirement, and no mandatory LLM credential.

## SDD and TDD workflow

`SPEC.md` remained the product contract, `AGENTS.md` the execution contract, and `TASKS.md` the dependency-ordered work plan. Each testable Task followed Red–Green–Refactor: tests were added first, an expected missing-behavior failure was observed, the minimum implementation was added, focused and historical suites were run, then structure and typing were improved without expanding behavior. Each Task updated `progress.md`, received a dedicated Conventional Commit, and was pushed before the next Task.

This sequence prevented later layers from dictating earlier contracts. For example, the API consumes the same Pydantic records validated by the parser, agent, and repository rather than maintaining parallel response dictionaries.

## Key design decisions

### Explicit boundaries

Network transport, clocks, sleepers, LLM clients, scheduler waiters, repositories, and browser timers/fetch functions are injectable. This made timeout, retry, overlap, stale recovery, and dependency failures deterministic without live services.

### Identity separate from content

Stable identity prefers source plus source event ID; otherwise it uses source/title and stable publication/link fields. A separate material fingerprint includes normalized title, description, status, services, regions, and publication time. This cleanly supports insert, re-analyze/update, and unchanged/skip behavior.

### One atomic validated record

SQLite stores the latest normalized incident and analysis together in one row, with indexed query columns. Read and write boundaries revalidate JSON. This keeps the local implementation small while guaranteeing that an incident and its analysis do not partially diverge.

### Conservative Decision Agent

The model prompt is deterministic, treats feed text as untrusted, defines all severities, forbids invention, and demands one schema-matching JSON object. Application code owns metadata and ID consistency. Any failure produces a full fallback rather than partial model output. The fallback deliberately reports uncertainty and asks operators to verify actual local impact.

### No-build accessible dashboard

The dashboard uses semantic HTML and native controls. Renderers construct nodes and assign `textContent`; no external text becomes HTML. The polling controller is portable enough to run under Node with injected fetch and timer functions, while the browser layer handles loading, empty, selection, stale, error, retry, and recovery states.

## Problems encountered and resolutions

The durable problem log is in `progress.md`. Notable examples:

- The base Python environment lacked pytest. A pinned dependency manifest and ignored virtual environment established a reproducible baseline.
- Pydantic Settings exposes `_env_file` dynamically, which mypy cannot see. Test-only construction was centralized behind one narrowly documented suppression.
- Inline HTML fragments initially gained a space before punctuation. The sanitizer was corrected to join inline fragments directly and insert separators only for block elements.
- Quality gates caught an unused test import and one unformatted dashboard test. Both were removed/fixed immediately and the entire suite was rerun.

Recording actual failures—including small quality failures—made the process auditable without inventing problems for appearances.

## What worked well

- Small dependency-ordered commits kept review scope clear.
- Schema reuse made validation consistent across RSS, storage, agent, and HTTP boundaries.
- Fakes and fixtures kept every default test offline and fast.
- Combining stable identity with fingerprinting made deduplication behavior easy to explain and verify.
- Treating failure states as first-class UI/API behavior produced a useful local demo even with RSS or LLM unavailable.
- Direct Node tests provided stronger polling evidence than static JavaScript inspection alone.

## Limitations and tradeoffs

- Public Azure status data is global and cannot establish tenant-specific impact.
- The bundled runtime is fallback-only; the provider-neutral `LLMClient` boundary is ready for a reviewed adapter, but no vendor SDK is shipped.
- Service and region detection uses a deliberately small known-name catalog rather than broad inference.
- Only the latest analysis is retained; there is no incident history table or audit timeline.
- The scheduler protects overlap in one process only. Multiple Uvicorn workers would each schedule ingestion.
- The dashboard retrieves at most 100 recent records per refresh and filters that view locally.
- The local server has no authentication and should bind only to a trusted loopback interface.

These tradeoffs preserve the specification's KISS/local-demo constraint and leave clear extension points.

## Lessons

1. A strict fallback contract is as important as the model success path; resilience comes from validated complete outputs, not exception suppression.
2. External text needs safety at every boundary: parser sanitization, schema validation, prompt delimiting, persistence validation, and DOM text rendering reinforce each other.
3. Time and scheduling code becomes straightforward once clocks and waits are explicit dependencies.
4. Operational health should distinguish unavailable local data from degraded external dependencies; users can still act on stored information.
5. Progress documentation is most useful when updated at Task boundaries with exact commands and symptoms, not reconstructed at the end.

## Recommended improvements

1. Add a reviewed provider adapter supporting schema/JSON mode without changing `LLMClient` or the fallback contract.
2. Discover services/regions from a maintained data file with tests for aliases and localization.
3. Add an optional incident-analysis history table and timeline view while retaining the current latest-record API.
4. Add browser-level accessibility and visual-regression automation in addition to static/Node checks.
5. Add explicit SQLite schema migrations if the local data model evolves beyond version 1.
6. Add opt-in live RSS smoke tests behind a marker, never in the default suite.

## Delivery conclusion

The system meets the approved local scope with traceable tasks, offline evidence, safe failure behavior, and documentation for setup, operation, demo, testing, architecture, prompts, limitations, and troubleshooting. Final commands and AC-001 through AC-018 results are recorded in `progress.md` and `SPEC.md`.
