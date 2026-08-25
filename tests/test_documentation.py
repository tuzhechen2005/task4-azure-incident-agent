from __future__ import annotations

import re
import subprocess
from pathlib import Path

from scripts.seed_demo import seed

ROOT = Path(__file__).parents[1]
README = (ROOT / "README.md").read_text()
RETROSPECTIVE = (ROOT / "docs" / "RETROSPECTIVE.md").read_text()
SPEC = (ROOT / "SPEC.md").read_text()


def test_readme_covers_required_operator_topics() -> None:
    for heading in (
        "Architecture and data flow",
        "Module responsibilities",
        "Data contracts",
        "Install",
        "Run locally",
        "Offline dashboard demo",
        "Configuration reference",
        "API",
        "Decision Agent and prompt strategy",
        "Dashboard behavior",
        "Failure behavior",
        "Test and quality commands",
        "Project structure",
        "Troubleshooting",
        "Security and limitations",
    ):
        assert f"## {heading}" in README or f"### {heading}" in README


def test_configuration_documentation_matches_settings_contract() -> None:
    for variable in (
        "AZURE_STATUS_RSS_URL",
        "RSS_TIMEOUT_SECONDS",
        "RSS_MAX_RETRIES",
        "INGESTION_INTERVAL_SECONDS",
        "DASHBOARD_POLL_SECONDS",
        "DATABASE_PATH",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_API_KEY",
        "LLM_TIMEOUT_SECONDS",
        "LLM_MAX_RETRIES",
        "LOG_LEVEL",
    ):
        assert f"`{variable}`" in README
        assert f"{variable}=" in (ROOT / ".env.example").read_text()


def test_referenced_local_paths_exist() -> None:
    for path in (
        "AGENTS.md",
        "SPEC.md",
        "TASKS.md",
        "progress.md",
        "docs/RETROSPECTIVE.md",
        "frontend/index.html",
        "scripts/seed_demo.py",
    ):
        assert (ROOT / path).exists(), path


def test_retrospective_covers_required_topics() -> None:
    for topic in (
        "Goal and outcome",
        "SDD and TDD workflow",
        "Key design decisions",
        "Conservative Decision Agent",
        "Problems encountered and resolutions",
        "Limitations and tradeoffs",
        "Lessons",
        "Recommended improvements",
    ):
        assert topic in RETROSPECTIVE


def test_offline_demo_seed_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "demo.db"

    assert seed(database) == 2
    assert seed(database) == 2


def test_acceptance_checklist_is_complete() -> None:
    for number in range(1, 19):
        assert f"- [x] AC-{number:03d}" in SPEC


def test_tracked_delivery_manifest_excludes_generated_or_secret_files() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    forbidden_parts = {".env", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache"}
    forbidden_suffixes = {".db", ".sqlite", ".sqlite3", ".log", ".zip"}

    assert not any(
        any(part in Path(name).parts for part in forbidden_parts) for name in tracked
    )
    assert not any(Path(name).suffix in forbidden_suffixes for name in tracked)


def test_tracked_text_has_no_common_secret_tokens() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    pattern = re.compile(r"(?:gho_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})")

    for name in tracked:
        path = ROOT / name
        if path.is_file():
            assert not pattern.search(path.read_text(errors="ignore")), name
