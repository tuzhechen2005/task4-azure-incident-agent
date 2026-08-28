from __future__ import annotations

import re
import subprocess
from pathlib import Path

from scripts.seed_demo import seed

ROOT = Path(__file__).parents[1]
README = (ROOT / "README.md").read_text()
RETROSPECTIVE = (ROOT / "docs" / "RETROSPECTIVE.md").read_text()
SPEC = (ROOT / "SPEC.md").read_text()


def delivery_files() -> list[str]:
    """List committed files, or archive files when Git metadata is absent."""
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True
    )
    if result.returncode == 0:
        return result.stdout.splitlines()

    runtime_directories = {"__pycache__", ".pytest_cache", ".mypy_cache"}
    return [
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(
            part in runtime_directories for part in path.relative_to(ROOT).parts
        )
    ]


def test_readme_covers_required_operator_topics() -> None:
    for heading in (
        "架构与数据流",
        "模块职责",
        "数据契约",
        "安装",
        "本地运行",
        "离线监控面板演示",
        "配置参考",
        "API 接口",
        "Decision Agent 与提示词策略",
        "监控面板行为",
        "失败处理",
        "测试与质量检查命令",
        "项目结构",
        "常见问题排查",
        "安全与限制",
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
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_KEY",
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
        "目标与成果",
        "SDD 与 TDD 工作流",
        "关键设计决策",
        "保守的 Decision Agent",
        "遇到的问题与解决办法",
        "限制与权衡",
        "经验总结",
        "后续改进建议",
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
    tracked = delivery_files()
    forbidden_parts = {".env", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache"}
    forbidden_suffixes = {".db", ".sqlite", ".sqlite3", ".log", ".zip"}

    assert not any(
        any(part in Path(name).parts for part in forbidden_parts) for name in tracked
    )
    assert not any(Path(name).suffix in forbidden_suffixes for name in tracked)


def test_tracked_text_has_no_common_secret_tokens() -> None:
    tracked = delivery_files()
    pattern = re.compile(r"(?:gho_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})")

    for name in tracked:
        path = ROOT / name
        if path.is_file():
            assert not pattern.search(path.read_text(errors="ignore")), name
