"""Validated Decision Agent with bounded repair and deterministic fallback."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.agents.client import LLMClient, LLMError
from app.agents.prompts import build_prompts
from app.models.schemas import (
    AgentInput,
    AnalysisSource,
    IncidentAnalysis,
    IncidentStatus,
    ResponsePlan,
    Severity,
)


class DecisionAgent:
    """Convert model responses into trusted analyses or safe local fallbacks."""

    def __init__(
        self,
        *,
        client: LLMClient | None,
        timeout_seconds: float,
        max_retries: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must not be negative")
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def analyze(self, agent_input: AgentInput) -> IncidentAnalysis:
        """Return validated LLM output, falling back for every controlled failure."""
        if self._client is None:
            return self._fallback(agent_input, "missing credentials or client")

        prompts = build_prompts(agent_input)
        user_prompt = prompts.user
        last_reason = "invalid response"
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.generate(
                    system_prompt=prompts.system,
                    user_prompt=user_prompt,
                    timeout_seconds=self._timeout_seconds,
                )
                return self._validate_response(
                    content=response.content,
                    model=response.model,
                    agent_input=agent_input,
                )
            except LLMError as error:
                last_reason = error.category.value.lower().replace("_", " ")
                if not error.retryable:
                    break
            except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
                last_reason = "invalid model response"
            except Exception:
                last_reason = "provider error"

            if attempt < self._max_retries:
                user_prompt = (
                    f"{prompts.user}\n\nThe previous response was invalid ({last_reason}). "
                    "Repair it and return one complete JSON object matching the contract."
                )

        return self._fallback(agent_input, last_reason)

    def _validate_response(
        self,
        *,
        content: str,
        model: str | None,
        agent_input: AgentInput,
    ) -> IncidentAnalysis:
        payload: Any = json.loads(content)
        if not isinstance(payload, dict):
            raise ValueError("model response must be one JSON object")
        payload["analyzed_at"] = self._now()
        payload["analysis_source"] = AnalysisSource.LLM
        payload["model"] = model
        analysis = IncidentAnalysis.model_validate(payload)
        if analysis.incident_id != agent_input.incident_id:
            raise ValueError("analysis incident_id does not match input")
        return analysis

    def _fallback(self, agent_input: AgentInput, reason: str) -> IncidentAnalysis:
        active_or_monitoring = agent_input.status in {
            IncidentStatus.ACTIVE,
            IncidentStatus.MONITORING,
        }
        severity = Severity.SEV_3 if active_or_monitoring else Severity.SEV_4
        confidence = 0.25 if active_or_monitoring else 0.35
        reason_label = {
            "missing credentials or client": "未配置凭据或客户端",
            "invalid model response": "模型响应无效",
            "provider error": "提供商错误",
            "timeout": "请求超时",
            "provider": "提供商不可用",
            "rate limit": "达到调用频率限制",
            "authentication": "身份验证失败",
            "invalid response": "响应无效",
        }.get(reason, "分析服务不可用")
        impact = (
            ["匹配的工作负载可能受到影响，请结合本地遥测数据核实。"]
            if active_or_monitoring
            else ["当前公共通知未确认仍有活跃的工作负载影响。"]
        )
        return IncidentAnalysis(
            incident_id=agent_input.incident_id,
            severity=severity,
            confidence=confidence,
            affected_services=agent_input.services,
            affected_regions=agent_input.regions,
            scope="仅依据公共状态信息，尚未确认具体租户的实际影响范围。",
            summary=agent_input.title,
            potential_impact=impact,
            recommended_actions=[
                "通过应用和平台遥测数据核实实际影响。",
                "持续关注关联的公共状态来源。",
                "若确认本地业务受影响，请通过既定支持渠道升级处理。",
            ],
            response_plan=ResponsePlan(
                immediate_actions=["确认受影响的服务和区域是否与已部署工作负载匹配。"],
                investigation_steps=["检查错误率、延迟、可用性以及近期部署变更。"],
                mitigation_options=[
                    "仅使用预先批准的重试、故障转移或工作负载绕行方案。"
                ],
                communication_plan=[
                    "同步已核实的本地影响并引用公共来源，不夸大影响范围。"
                ],
                recovery_checks=["宣布恢复前，确认本地指标已回到基线。"],
                escalation_conditions=[
                    "若影响扩大、关键工作负载停止或数据完整性面临风险，应立即升级。"
                ],
            ),
            rationale=(
                "由于没有可用的有效模型评估，系统依据规范化状态采用保守的备用严重级别。"
            ),
            analyzed_at=self._now(),
            analysis_source=AnalysisSource.FALLBACK,
            model=None,
            warnings=[
                f"已使用确定性备用分析：{reason_label}。",
                "公共状态数据无法确认具体租户的实际影响。",
            ],
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now.astimezone(timezone.utc)
