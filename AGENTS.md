# AI Development Instructions

This repository contains the **Azure Incident Response Agent and Local Monitoring Dashboard** project. These instructions apply to every AI coding session in this repository.

## Repository Safety

- Treat every file under `sources/` as read-only reference material.
- Do not edit, rename, move, or delete files under `sources/`.
- Do not copy code from Tasks 1–3 wholesale. Reuse only small, generic modules after verifying that they satisfy this project's specification and tests.
- Never expose secrets, API keys, connection strings, or private incident data in code, tests, logs, screenshots, or documentation.

## Required Methodology

This project uses **Spec-Driven Development (SDD)** for scope and contracts and **Test-Driven Development (TDD)** for implementation.

- `SPEC.md` defines what the finished system must do.
- `TASKS.md` defines the implementation units, dependencies, required tests, and progress.
- Tests are executable evidence that an implementation satisfies the specification.
- Implementation must not begin until the human has approved the specification.

## Session Context Recovery

At the beginning of every implementation session:

1. Read this entire `AGENTS.md`.
2. Read the relevant sections of `SPEC.md`.
3. Read all of `TASKS.md` and find the first eligible `TODO` task in the recommended order.
4. Inspect the existing files related to that task; do not trust remembered chat context.
5. Check the working tree and preserve unrelated user changes.
6. Run the existing test suite and record the baseline. If it already fails, report the failure and determine whether the current task can safely continue.
7. Restate the selected task's scope, dependencies, files, acceptance criteria, and tests before changing code.

The repository is the durable project memory. Conversation history is supporting context only.

## Goal Mode and Sequential Task Rule

- Work on exactly one `TASK-XXX` at a time.
- Select a task only when all listed dependencies are `DONE`.
- Do not implement later tasks, speculative abstractions, or unrelated cleanup.
- Do not change files outside the task's `Files` list unless the task cannot be completed otherwise. If an extra file is required, explain why before changing it and record it in `TASKS.md`.
- If a task affects more than three production modules, first write a short implementation plan listing files, interfaces, tests, and risks.
- When a Goal is active, treat the Goal as the stopping boundary and each `TASK-XXX` as a sequential checkpoint.
- Complete only one task at a time. After its Definition of Done is satisfied and its commit is created, immediately select the next eligible `TODO` task and repeat Red–Green–Refactor.
- Do not pause for confirmation between tasks unless a blocker, specification conflict, destructive action, missing authority, or material product decision requires human input.
- Continue until the Goal is genuinely complete, every task in its scope is `DONE`, or progress is genuinely blocked.
- Provide concise progress updates between tasks so the human can see the completed task, test result, commit, and next task.

## Red–Green–Refactor Workflow

Every testable task must follow this sequence.

### RED — write a failing test first

1. Translate the task's acceptance criteria into tests.
2. Add only the tests needed for the current task.
3. Run the new tests before production implementation.
4. Confirm that they fail for the expected missing behavior, not because of an unrelated syntax, import, fixture, or environment error.
5. Record the failing command and concise reason in the completion report.

Do not write production behavior first and backfill tests later. A documentation-only task may replace RED with a documented validation checklist.

### GREEN — implement the minimum behavior

1. Write the smallest implementation that satisfies the current tests and specification.
2. Do not implement future requirements in advance.
3. Run focused tests until they pass.
4. Run all previously passing tests to detect regressions.

### REFACTOR — improve without changing behavior

- Remove duplication and improve naming, typing, structure, and readability only where relevant to the current task.
- Do not change public contracts or expand scope.
- Run focused and full tests again after refactoring.

## Testing Rules

- Unit tests must be deterministic, isolated, and runnable offline.
- RSS tests must use fixtures and mocked HTTP responses; never depend on a live feed.
- Decision Agent tests must mock the LLM client; never consume a real API in the default test suite.
- Time, randomness, and scheduler behavior must be controllable in tests.
- Storage tests must use a temporary database, never the user's working database.
- API tests must verify status codes and response schemas, including empty and error states.
- Tests must cover success, boundary, invalid-input, timeout, dependency-failure, duplicate, and fallback behavior where relevant.
- Optional live integration tests must be clearly marked and excluded from the default test command.

## Source of Truth and Conflict Handling

For product behavior, use this priority:

1. Human's latest explicit requirement
2. `SPEC.md`
3. The current task in `TASKS.md`
4. Existing tests
5. Existing implementation

This `AGENTS.md` is authoritative for development process and repository safety.

If two sources conflict:

- Stop before implementing the conflicting behavior.
- Describe the conflict and its practical effect.
- Do not silently change `SPEC.md`, reinterpret acceptance criteria, weaken a test, or preserve incorrect existing behavior.
- Obtain human approval for a specification change, then update `SPEC.md` and affected tasks before implementation.

## Engineering Constraints

- Follow the KISS principle. This is a local, demonstrable project, not a production-scale Azure platform.
- Use the architecture and contracts in `SPEC.md`; do not introduce microservices, containers, Redis, Kafka, Kubernetes, or a frontend framework unless the specification is explicitly amended.
- Keep external integrations behind interfaces so they can be mocked.
- Validate all data crossing RSS, LLM, persistence, and HTTP boundaries.
- Prefer explicit, readable code over premature generalization.
- Keep configuration outside source code and provide safe documented defaults.
- Log operational events without logging secrets or full sensitive payloads.

## Code Quality Standards

### General

- Keep functions and modules focused on one responsibility; prefer composition over hidden global state.
- Use descriptive names and remove dead code, commented-out code, debug prints, and unused dependencies before committing.
- Keep public contracts explicit. Validate data at external boundaries and avoid catching exceptions without handling or re-raising them meaningfully.
- Comments must explain intent or constraints, not restate obvious code. Public modules, classes, and non-obvious functions require concise documentation.
- Use UTF-8, a final newline, consistent formatting, and no trailing whitespace.
- Never weaken tests, disable checks, or add broad ignore rules merely to make validation pass.

### Python

- Follow PEP 8 and the project-configured formatter/linter. Use a maximum line length of 100 unless generated content requires otherwise.
- Add type hints to public functions, methods, constructors, and important internal boundaries. Avoid untyped dictionaries when a declared schema exists.
- Order imports as standard library, third-party, then local modules; do not use wildcard imports.
- Prefer small pure functions for parsing and normalization. Inject network, clock, LLM, scheduler, and storage dependencies for testability.
- Use `pathlib` for paths, timezone-aware UTC datetimes, structured logging instead of `print`, and context managers for resources.

### HTML, CSS, and JavaScript

- Use semantic HTML, accessible labels, keyboard-visible focus, and responsive layouts.
- Use `const` by default and `let` only for reassignment; avoid implicit globals and keep API/state/rendering concerns separate.
- Never place untrusted RSS or LLM content into `innerHTML`; render it through safe text APIs.
- Keep CSS selectors and component names predictable; avoid inline styles and unnecessary duplication.

### Tests

- Name tests after observable behavior and keep Arrange–Act–Assert structure clear.
- A test must have one primary behavioral reason to fail. Reuse fixtures without hiding important setup.
- Run formatting, linting, type checks, focused tests, and the full default suite when those checks are configured for the project.

## Git and Commit Discipline

- The repository must maintain a readable history with one logical completed task per commit.
- Before starting a task, inspect `git status`, the current branch, and recent history. Preserve unrelated user changes and never include them in a task commit.
- Do not commit during RED while tests intentionally fail. Commit only after GREEN/REFACTOR, all required checks pass, and `TASKS.md` is updated to `DONE`.
- Stage files explicitly by path. Review the staged diff and verify that it contains only the current task, its tests, and required documentation/status updates.
- Use Conventional Commit style: `<type>(<scope>): <summary>`, with the task ID in the summary or body. Example: `feat(config): complete TASK-001 project configuration`.
- Use `feat` for new behavior, `fix` for corrections, `test` for test-only changes, `refactor` for behavior-preserving restructuring, `docs` for documentation, and `chore` for tooling or maintenance.
- Keep the subject imperative, specific, and concise. Add a body when decisions, migration notes, risks, or verification commands need explanation.
- Do not bundle multiple completed tasks into one commit. Do not amend, squash, rebase, force-push, or rewrite existing history unless the human explicitly requests it.
- Never commit secrets, `.env`, local databases, logs, caches, virtual environments, or generated artifacts.
- Creating local commits is required during Goal execution. Pushing commits, creating branches, tags, pull requests, or releases requires explicit human instruction unless the active Goal explicitly includes it.
- If commit creation fails, keep the task work intact, report the failure, and resolve it before advancing to the next task.

## Status Management

Valid task states are `TODO`, `IN PROGRESS`, `BLOCKED`, and `DONE`.

- Change a task from `TODO` to `IN PROGRESS` only when work begins.
- Use `BLOCKED` only when a concrete unmet dependency or required human decision prevents safe progress; document the blocker.
- Change a task to `DONE` only after every Definition of Done item is satisfied.
- Do not mark dependent tasks complete automatically.
- Preserve task history and do not renumber task IDs after implementation begins.

## Definition of Done

A task is `DONE` only when all applicable items are true:

- [ ] All dependencies were already `DONE`.
- [ ] Every acceptance criterion is satisfied.
- [ ] Required tests were written before production implementation.
- [ ] The RED failure was observed and was caused by the missing behavior.
- [ ] Focused tests pass.
- [ ] The full default test suite passes.
- [ ] Relevant invalid-input, timeout, duplicate, and fallback cases are covered.
- [ ] No unrelated or future-task functionality was added.
- [ ] Refactoring, if performed, preserved behavior and tests still pass.
- [ ] Configuration and documentation affected by the task are current.
- [ ] No secrets, generated databases, caches, or build artifacts were committed.
- [ ] `TASKS.md` status was updated accurately.
- [ ] Formatting, linting, and type checks configured for the project pass.
- [ ] The staged diff contains only the current task's changes.
- [ ] The completed task is recorded in one logical Conventional Commit.

## Task Checkpoint Report

After each task, report this checkpoint and then continue to the next eligible task while the Goal remains active:

1. Completed task ID and title.
2. Files added or changed.
3. Tests written first.
4. RED command and expected failure reason.
5. Minimum implementation added for GREEN.
6. Refactoring performed, or `None`.
7. Focused and full test results.
8. Acceptance-criteria checklist.
9. Commit hash and subject.
10. Next task selected, or the reason the Goal is complete/blocked.

At the end of the Goal, provide one consolidated report covering all completed tasks, commits, validation results, remaining risks, and any intentionally unfinished work.

## Prohibited Actions

- Do not implement business code while the specification is awaiting approval.
- Do not work on multiple tasks concurrently. Goal mode may complete multiple tasks sequentially in one continuous run.
- Do not call a live LLM or live RSS feed from the default tests.
- Do not make destructive repository changes or overwrite unrelated user work.
- Do not mark a task `DONE` merely because code was written.
- Do not stop after a successful task checkpoint while an active Goal still has eligible tasks in scope.
