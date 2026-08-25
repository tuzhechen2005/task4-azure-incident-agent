from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]
HTML = ROOT / "frontend" / "index.html"
CSS = ROOT / "frontend" / "styles.css"
JS = ROOT / "frontend" / "app.js"
MOCK = ROOT / "tests" / "fixtures" / "dashboard_mock.json"


def test_dashboard_has_required_regions() -> None:
    html = HTML.read_text()

    for element in ("<header", "<main", "<table", "<aside", "<footer"):
        assert element in html
    for region_id in (
        "systemHealth",
        "summaryCards",
        "incidentFilters",
        "incidentList",
        "incidentDetail",
        "responsePlan",
        "loadingState",
        "emptyState",
        "errorState",
        "staleState",
        "noSelectionState",
    ):
        assert f'id="{region_id}"' in html


def test_dashboard_has_accessible_labels() -> None:
    html = HTML.read_text()

    for control_id in (
        "severityFilter",
        "statusFilter",
        "serviceFilter",
        "regionFilter",
    ):
        assert f'for="{control_id}"' in html
        assert f'id="{control_id}"' in html
    assert 'aria-live="polite"' in html
    assert 'type="button"' in html
    assert ":focus-visible" in CSS.read_text()


def test_dashboard_is_simplified_chinese() -> None:
    html = HTML.read_text()
    javascript = JS.read_text()

    assert '<html lang="zh-CN">' in html
    for label in ("Azure 事件响应中心", "筛选条件", "事件列表", "响应计划"):
        assert label in html
    for message in ("正在加载", "刷新失败", "仅本地备用分析"):
        assert message in javascript


def test_dashboard_loads_local_assets() -> None:
    html = HTML.read_text()

    assert 'href="/static/styles.css"' in html
    assert 'src="/static/app.js"' in html
    assert "https://" not in html


def test_dashboard_does_not_render_dynamic_inner_html() -> None:
    javascript = JS.read_text()

    assert "innerHTML" not in javascript
    assert "textContent" in javascript
    assert "replaceChildren" in javascript


def test_severity_has_text_label() -> None:
    javascript = JS.read_text()

    for value in ("SEV-1 严重", "SEV-2 高", "SEV-3 中", "SEV-4 低"):
        assert value in javascript


def test_dashboard_represents_all_states() -> None:
    javascript = JS.read_text()

    for state in ("loading", "empty", "error", "stale", "selected", "no-selection"):
        assert state in javascript


def test_mock_data_maps_every_detail_section() -> None:
    mock = json.loads(MOCK.read_text())
    javascript = JS.read_text()

    assert set(mock) == {"health", "stats", "record"}
    for field in (
        "potential_impact",
        "recommended_actions",
        "rationale",
        "scope",
        "warnings",
    ):
        assert field in mock["record"]["analysis"]
        assert field in javascript
    for field in (
        "immediate_actions",
        "investigation_steps",
        "mitigation_options",
        "communication_plan",
        "recovery_checks",
        "escalation_conditions",
    ):
        assert field in mock["record"]["analysis"]["response_plan"]
        assert field in javascript
