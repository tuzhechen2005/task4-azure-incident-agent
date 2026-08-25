from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_dashboard_polling_node_suite() -> None:
    result = subprocess.run(
        ["node", "--test", "tests/frontend/test_dashboard_polling.js"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    for name in (
        "test_poll_on_initial_load",
        "test_poll_at_configured_interval",
        "test_poll_prevents_overlap",
        "test_poll_error_retains_last_data",
        "test_poll_recovers",
    ):
        assert name in result.stdout
