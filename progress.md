# Goal 进度记录

## Goal 概览

- 项目目标：交付 `SPEC.md` 与 `TASKS.md` 规定的本地 Azure 事件响应智能体和监控面板。
- 开始时间：2026-08-25（Asia/Shanghai）。
- 当前状态：已完成 TASK-017；等待提交与推送记录。
- 当前分支：`main`。
- GitHub 仓库：`tuzhechen2005/task4-azure-incident-agent`。
- 已完成任务：17；剩余任务：0。

## 任务进度

| Task | 状态 | 交付内容 | 验证与提交 |
|---|---|---|---|
| TASK-001 | DONE | 配置、日志、忽略规则、测试基础。 | 11 项测试和质量检查通过；`9499094`。 |
| TASK-002 | DONE | Pydantic 领域 schema 与校验。 | schema 测试与质量检查通过。 |
| TASK-003 | DONE | 可注入 RSS 客户端和错误映射。 | mock HTTP 场景通过。 |
| TASK-004 | DONE | RSS/Atom 解析、条目隔离与 fixture。 | 空 feed、坏 XML、坏条目通过。 |
| TASK-005 | DONE | 事件标准化、稳定身份和 fingerprint。 | 去重与状态映射通过。 |
| TASK-006 | DONE | SQLite 初始化、原子仓库、查询与统计。 | 持久化、回滚、分页和筛选通过。 |
| TASK-007 | DONE | `LLMClient` 接口与安全提示词。 | 提示词契约与假客户端通过。 |
| TASK-008 | DONE | Decision Agent、JSON 校验和 fallback。 | 四级严重度与异常场景通过。 |
| TASK-009 | DONE | 抓取到持久化的事件处理编排。 | 新增、变化、重复、失败隔离通过。 |
| TASK-010 | DONE | 启动抓取、定期调度和关闭。 | 不重叠与异常恢复通过。 |
| TASK-011 | DONE | FastAPI 工厂、生命周期和安全错误。 | 生命周期及静态路径通过。 |
| TASK-012 | DONE | `/api/health` 与 `/api/stats`。 | 健康、降级和统计通过。 |
| TASK-013 | DONE | 事件列表和详情接口。 | 过滤、分页、404 和 schema 通过。 |
| TASK-014 | DONE | 可访问中文面板和安全渲染。 | 静态面板检查通过。 |
| TASK-015 | DONE | 轮询、失败保留与端到端 fixture 流程。 | 轮询、重复、重启持久化通过。 |
| TASK-016 | DONE | README、复盘、离线演示和交付审计。 | 全量测试、质量检查和验收清单完成。 |
| TASK-017 | DONE | Azure OpenAI Responses API 适配器、严格 JSON Schema、配置、应用接线与文档。 | RED 按预期失败；160 项 Python、5 项 Node 测试及全部质量检查通过；提交待补录。 |

### TASK-017 详细记录

- 开始/完成时间：2026-08-28（Asia/Shanghai）。
- RED：`.venv/bin/python -m pytest -q tests/unit/test_azure_openai.py tests/unit/test_config.py tests/integration/test_health_stats_api.py` 在收集阶段因 `app.agents.azure_openai` 不存在而失败，证明真实适配器尚未实现。
- GREEN：新增 Azure OpenAI Responses API 客户端，以资源 `/openai/v1/` 为 base URL、以部署名为 `model`，发送 system/user prompt 和严格 JSON Schema；将 provider 异常映射到既有安全错误类型；配置完整时应用自动接线，缺失时保持 fallback-only。
- REFACTOR：以协议注入 SDK 客户端，统一 Endpoint 规范化、输出提取、错误脱敏和响应 schema 构造。
- 文档：更新 `.env.example`、README、规格和复盘，说明真实模式与离线降级模式。
- 聚焦测试：32 项通过；完整测试：160 项 Python 与 5 项 Node 通过。
- 质量检查：Ruff format、Ruff lint、mypy、`node --check`、`pip check` 全部通过。
- 本地运行：在无凭据且 RSS 不可用时 `/api/health` 返回 `200` 与 `fallback-only`，服务保持可用。
- 云端验证：当前环境三项 Azure 凭据均未设置，因此没有执行计费的真实云请求；SDK 构造、请求结构、错误映射和应用接线均通过离线测试。

## 实际问题、踩坑与解决方案

### P-001：基础 Python 环境没有测试运行器

症状：初次执行测试时无法找到 `pytest`。根因是干净环境未安装项目依赖。解决：在 `requirements.txt` 明确开发所需依赖，并通过虚拟环境执行文档化命令；避免依赖全局环境。

### P-002：初次质量检查发现格式与动态配置类型问题

症状：formatter 与类型检查报告不一致。根因是设置对象和运行时注入边界不够明确。解决：统一 formatter、补充类型标注，并让测试通过显式设置构造配置。

### P-003：HTML 文本提取在标点前插入空白

症状：RSS 描述清理后的标点前有额外空格。根因是 HTML 转纯文本策略直接拼接节点。解决：规范化空白并清理中文/英文标点前空格，新增回归测试。

### P-004：仓库测试残留未使用导入

症状：lint 失败。根因是重构后测试辅助导入未删除。解决：移除无用导入，并将 lint 纳入每个任务的完成条件。

### P-005：新增面板静态测试后格式检查失败

症状：测试文件格式不符合项目规范。根因是新增测试未先运行 formatter。解决：提交前统一运行 formatter、lint、类型检查与完整测试。

### P-006：健康接口分析模式可能与运行时不一致

症状：打包后的分析模式和依赖注入对象可能不同。根因是健康数据来自静态配置而不是实际运行服务。解决：健康接口读取当前服务状态，并使用测试覆盖 fallback 模式。

### P-007：归档测试假设存在 Git 元数据

症状：无 `.git` 的打包环境验证失败。根因是测试把开发环境假设带入交付环境。解决：测试仅检查应交付文件与禁止文件，不依赖 Git 元数据。

### P-008：中文化时遗漏机器校验的验收清单

症状：文档测试找不到 `AC-001` 至 `AC-018` 的勾选项。根因是中文化时将详细清单压缩成了概述，破坏了文档的机器可验证契约。解决：恢复全部中文验收项并保留原有 `- [x] AC-XXX` 标记；以后翻译文档时不得删除被测试引用的稳定标识。

### P-009：空 Azure Endpoint 被 URL 校验当作非法值

症状：`.env` 中保留空的 `AZURE_OPENAI_ENDPOINT=` 时配置模型直接报 URL 校验错误，无法进入 fallback-only。根因是可选 URL 字段没有在 Pydantic URL 解析前将空字符串标准化为 `None`。解决：增加 `mode="before"` 字段校验器，并测试 Endpoint、Deployment、Key 任一缺失都会安全进入 fallback。

## 关键决定

- D-001：在空仓库上初始化 `main`，仓库名与文件夹名均为 `task4-azure-incident-agent`。
- D-002：使用 Pydantic Settings 管理配置，便于类型校验、环境覆盖与 fallback-only 模式。
- D-003：使用 SQLite 而非外部数据库，满足本地演示、持久化、去重和查询需求。
- D-004：将 LLM 放在 `LLMClient` 边界后，默认测试只验证应用行为而不调用真实模型。
- D-005：真实路径采用 Azure OpenAI Responses API 与严格 JSON Schema；默认离线测试使用可注入假 SDK，真实凭据只放在本地环境。

## 最终验证

已执行 160 项完整离线 Python 测试、5 项 Node 轮询测试、格式化、lint、类型检查、依赖检查、本地启动、fixture 到 API/面板流程、fallback-only 模式、SQLite 重启持久化以及交付审计。AC-001 至 AC-018 均已记录为通过；交付物不包含 `.env`、秘密、本地数据库、缓存、日志、虚拟环境或生成文件。真实 Azure OpenAI 云请求需要调用者配置自己的资源与凭据，当前环境未执行计费调用。
