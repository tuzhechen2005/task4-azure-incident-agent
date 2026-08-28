# Goal 进度记录

## Goal 概览

- 项目目标：交付 `SPEC.md` 与 `TASKS.md` 规定的本地 Azure 事件响应智能体和监控面板。
- 开始时间：2026-08-25（Asia/Shanghai）。
- 当前状态：已完成 TASK-019；Azure RSS 与 DeepSeek 真实链路已验证成功。
- 当前分支：`main`。
- GitHub 仓库：`tuzhechen2005/task4-azure-incident-agent`。
- 已完成任务：19；剩余任务：0。

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
| TASK-017 | DONE | Azure OpenAI Responses API 适配器、严格 JSON Schema、配置、应用接线与文档。 | RED 按预期失败；160 项 Python、5 项 Node 测试及全部质量检查通过；`3860ff3`。 |
| TASK-018 | DONE | DeepSeek V4 Pro 直连、移除 Azure 托管配置、应用接线与中文文档。 | RED 按预期失败；160 项 Python、5 项 Node 测试及全部质量检查通过。 |
| TASK-019 | DONE | Azure RSS 安全 HTTPS 传输与真实端到端运行验证。 | 10 项聚焦测试、163 项 Python、5 项 Node、真实微软 RSS、两次 DeepSeek 调用、SQLite、API、面板和重启去重均通过。 |

### TASK-019 实施计划

- 生产文件：仅替换 `app/ingestion/rss_client.py` 的默认 HTTP 传输，保留 `RSSClient` 和既有异常契约。
- 接口：继续使用 `HTTPTransport.get` 与 `HTTPResponse`，上层采集、解析、调度和 API 无需改变。
- 测试：先为默认 httpx 传输添加成功、超时、网络异常、请求头、重定向和状态码测试并观察 RED；实现后运行既有 RSS、完整离线测试和真实 RSS 冒烟验证。
- 风险：微软公共 RSS 在没有广泛事件时会返回合法但无 `<item>` 的 feed，因此真实 RSS 成功只证明采集链；真实 DeepSeek 链路将使用本地受控 feed 和临时数据库单独验证。

### TASK-019 详细记录

- 开始/完成时间：2026-08-29（Asia/Shanghai）。
- 根因：微软官方 RSS 经 `curl` 返回 HTTP 200，但框架 Python 的 `urllib` 没有正确使用 macOS 信任链，抛出 `SSLCertVerificationError: self-signed certificate in certificate chain`；同一虚拟环境中的 httpx 能在保持 TLS 校验的情况下成功连接。
- RED：`.venv/bin/python -m pytest -q tests/unit/test_rss_client.py` 在收集阶段因 `HTTPXTransport` 不存在而失败，证明安全替代传输尚未实现。
- GREEN：新增默认 `HTTPXTransport`，启用安全 TLS 默认值与重定向，将 httpx 超时和网络异常映射回既有 `TimeoutError`/`OSError` 边界；`RSSClient` 的重试、状态码和空正文行为保持不变。
- REFACTOR：移除仅用于旧传输的 `urllib` 代码，继续复用既有 `HTTPTransport` 与 `HTTPResponse`，上层解析、服务和调度无需改动。
- 真实 RSS：`https://azure.status.microsoft/en-us/status/feed/` 返回 HTTP 200、577 字节合法 XML、0 条活动事件、0 条解析警告；生产服务最近成功采集时间已更新，`last_error=null`。
- 真实模型：受控 fixture 通过本地 HTTP 源触发两次 DeepSeek V4 Pro Responses API 调用，均返回 HTTP 200；两条分析均以 `analysis_source=LLM`、`model=deepseek-v4-pro` 写入临时 SQLite。
- API 与面板：健康、统计、列表、详情、首页和 JavaScript 均返回 200；浏览器实际渲染健康状态、2 条事件、严重度、模型摘要和完整六部分响应预案。
- 重启验证：复用同一临时数据库后得到 `inserted=0 updated=0 unchanged=2 failed=0`，没有重复调用模型；临时进程已关闭，临时数据已移入系统废纸篓。
- 完整验证：163 项 Python 与 5 项 Node 测试通过；Ruff format、Ruff lint、mypy、`node --check`、`pip check`、`git diff --check` 和秘密扫描全部通过。
- 安全：真实 Key 仅从被忽略的 `.env` 读取，命令、日志、测试输出和文档均未显示或保存 Key。
- 提交：本次 TASK-019 独立 Conventional Commit（hash 见 Git 历史）；按 Goal 要求在提交后推送 `main`。

### TASK-018 实施计划

- 生产文件：新增 `app/agents/deepseek.py`，修改配置、应用工厂和启动日志脱敏，移除 Azure OpenAI 专用适配器。
- 接口：保留既有 `LLMClient.generate` 契约和严格 JSON Schema；运行配置改为 `LLM_PROVIDER`、`LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`。
- 测试：先替换为 DeepSeek 配置、适配器、应用接线和文档契约测试，观察因实现缺失而产生的有效 RED，再完成最小实现并运行全量检查。
- 风险：提供商兼容层可能与 OpenAI SDK 参数存在差异；通过可注入假 SDK 验证请求，不在默认测试中调用计费 API，真实调用失败时继续安全 fallback。

### TASK-018 详细记录

- 开始/完成时间：2026-08-29（Asia/Shanghai）。
- RED：`.venv/bin/python -m pytest -q tests/unit/test_deepseek.py tests/unit/test_config.py tests/integration/test_health_stats_api.py tests/test_documentation.py` 在收集阶段因 `app.agents.deepseek` 不存在而失败，证明 DeepSeek 直连尚未实现。
- GREEN：新增 DeepSeek Responses API 适配器，以 `https://api.deepseek.com` 为默认 Base URL、以 `deepseek-v4-pro` 为默认模型，复用 system/user prompt、严格 JSON Schema、错误映射和安全 fallback；应用工厂改为按 `LLM_PROVIDER=deepseek` 接线。
- REFACTOR：移除 Azure OpenAI Endpoint、Deployment、Key 及专用适配器，统一为 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`，并保持提供商中立的 `LLMClient` 契约。
- 文档：更新 `.env.example`、README、规格与复盘，明确 Azure 只作为被监控的数据源，真实智能体直接调用 DeepSeek，不要求 Azure 订阅或模型部署。
- 聚焦测试：40 项通过；完整测试：160 项 Python 与 5 项 Node 通过。
- 质量检查：Ruff format、Ruff lint、mypy、`node --check`、`pip check`、`git diff --check` 和秘密扫描全部通过。
- 云端验证：默认测试未调用计费 API；SDK 构造、请求结构、模型、输出提取和错误映射均通过可注入假 SDK 离线验证。
- 提交：本次 TASK-018 独立 Conventional Commit（hash 见 Git 历史）。

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
- 提交：`3860ff3` — `feat(agent): complete TASK-017 Azure OpenAI integration`。

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

### P-010：DeepSeek 生产代码完成后文档契约仍失败

症状：首轮 GREEN 中 39 项通过、文档配置测试因 README 缺少 `LLM_BASE_URL` 而失败。根因是代码配置已切换，但中文操作文档仍保留 Azure OpenAI 变量。解决：同步更新 README、`.env.example`、规格和复盘，并由文档测试验证全部环境变量一致。

### P-011：curl 能访问 RSS，但 Python 应用证书校验失败

症状：微软 RSS 经 curl 返回 200，应用却记录 `NetworkFetchError`。根因是当前 framework Python 的 OpenSSL 默认 CA 路径未正确接入 macOS 信任链，`urllib` 因自签名证书链报错。解决：使用项目已有 httpx 作为默认安全传输；其默认 CA 配置在本机验证成功，同时保持 TLS 校验、重定向、超时和异常映射，未使用 `verify=False`。

## 关键决定

- D-001：在空仓库上初始化 `main`，仓库名与文件夹名均为 `task4-azure-incident-agent`。
- D-002：使用 Pydantic Settings 管理配置，便于类型校验、环境覆盖与 fallback-only 模式。
- D-003：使用 SQLite 而非外部数据库，满足本地演示、持久化、去重和查询需求。
- D-004：将 LLM 放在 `LLMClient` 边界后，默认测试只验证应用行为而不调用真实模型。
- D-005：真实路径采用 Azure OpenAI Responses API 与严格 JSON Schema；默认离线测试使用可注入假 SDK，真实凭据只放在本地环境。
- D-006：根据用户最新要求，Azure 仅作为公共故障数据源；真实 Decision Agent 改为直接调用 DeepSeek V4 Pro Responses API，不再要求 Azure OpenAI 托管层。
- D-007：RSS 默认传输使用 httpx，而不是依赖 framework Python 不完整 CA 路径的 `urllib`；保持接口可注入且绝不关闭 TLS 校验。

## 最终验证

已执行 163 项完整离线 Python 测试、5 项 Node 轮询测试、格式化、lint、类型检查、依赖检查、真实微软 RSS、真实 DeepSeek 受控事件分析、SQLite 写入与重启去重、四个 API、浏览器面板、fallback-only 模式以及交付审计。AC-001 至 AC-018 均已记录为通过；交付物不包含 `.env`、秘密、本地数据库、缓存、日志、虚拟环境或生成文件。
