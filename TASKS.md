# 开发任务

## 工作约定

遵循 `AGENTS.md` 与 `SPEC.md`。每次只处理一个任务，并执行 Red–Green–Refactor；在活跃 Goal 中，任务测试与检查通过、状态更新、`progress.md` 更新并创建独立 Conventional Commit 后，自动进入下一个符合依赖的任务。状态为 `TODO`、`IN PROGRESS`、`BLOCKED`、`DONE`；仅在真实阻塞或重大冲突时暂停。

推荐顺序：`TASK-001 → TASK-002 → TASK-003 → TASK-004 → TASK-005 → TASK-006 → TASK-007 → TASK-008 → TASK-009 → TASK-010 → TASK-011 → TASK-012 → TASK-013 → TASK-014 → TASK-015 → TASK-016 → TASK-017`。

| Task | 状态 | 目标、依赖与必需验证 |
|---|---|---|
| TASK-001 | DONE | 项目骨架与配置；无依赖。验证默认值/覆盖/非法值/fallback/日志脱敏。 |
| TASK-002 | DONE | 领域 schema；依赖 001。验证事件、分析、枚举、时间、序列化和必填字段。 |
| TASK-003 | DONE | RSS HTTP 客户端；依赖 001。验证成功、超时、网络/HTTP/空响应和有限重试。 |
| TASK-004 | DONE | Feed 解析器；依赖 002、003。验证 RSS/Atom、空 feed、坏 XML、坏条目、纯文本和 UTC。 |
| TASK-005 | DONE | 标准化与身份；依赖 002、004。验证稳定 ID、fingerprint、状态映射和缺失字段。 |
| TASK-006 | DONE | SQLite 与仓库；依赖 001、002。验证初始化、原子 upsert、重启持久化、过滤、分页、统计和不存在记录。 |
| TASK-007 | DONE | `LLMClient` 边界与提示词；依赖 001、002。验证 schema、严重度、输入边界、假客户端与错误分类。 |
| TASK-008 | DONE | Decision Agent 与 fallback；依赖 002、007。验证四级严重度、非法 JSON、缺字段、错误 ID、超时、修复和确定性 fallback。 |
| TASK-009 | DONE | 事件处理服务；依赖 004、005、006、008。验证新增、批量、重复跳过、变化重分析、单条失败与周期统计。 |
| TASK-010 | DONE | 调度与生命周期；依赖 001、009。验证启动执行、间隔、禁止重叠、异常恢复、最近成功时间与关闭。 |
| TASK-011 | DONE | FastAPI 应用与错误处理；依赖 006、009、010。验证应用生命周期、依赖注入、request ID、安全错误和静态路径。 |
| TASK-012 | DONE | health/stats API；依赖 006、010、011。验证健康、降级、fallback、数据库不可用、空/有数据统计。 |
| TASK-013 | DONE | 事件列表/详情 API；依赖 006、011。验证空列表、排序、分页、过滤、非法参数、详情与 404。 |
| TASK-014 | DONE | 面板结构与渲染；依赖 012、013。验证可访问区域、安全渲染、严重度文本和状态转换。 |
| TASK-015 | DONE | 轮询与端到端集成；依赖 009、010、012、013、014。验证首次/定期轮询、禁止重叠、失败恢复、fixture pipeline、重复和重启。 |
| TASK-016 | DONE | 文档、复盘与交付审计；依赖全部前置任务。运行完整验证、核对 AC-001 至 AC-018、交付包与秘密扫描。 |
| TASK-017 | DONE | 接入真实 Azure OpenAI Decision Agent；依赖 007、008、011、016。配置、Responses API 请求、错误映射、应用接线、真实/降级模式和秘密保护均已验证。 |

每个 Task 的实现文件、验收标准和具体测试名称以代码、提交历史与 `progress.md` 中的已完成记录为准。任何后续变更都必须补充相应测试并按 TDD 创建独立任务或修复提交。

## TASK-017——真实 Azure OpenAI Decision Agent

**状态：DONE**

- **目标：** 在保留离线 fallback 的前提下，通过 Azure OpenAI Responses API 执行真实结构化事件分析。
- **文件：** `app/config.py`、`app/agents/azure_openai.py`、`app/api/app.py`、`main.py`、`.env.example`、`requirements.txt`、相关测试与中文文档。
- **依赖：** TASK-007、TASK-008、TASK-011、TASK-016。
- **实现要求：** 使用可注入 SDK 边界；发送 system/user prompt 与严格 JSON Schema；映射超时、限流、认证、连接和空响应错误；只有 provider、endpoint、deployment 和 key 全部有效时才启用真实模式。
- **验收标准：** 配置完整时默认应用创建真实客户端并报告 `azure_openai`；配置缺失或调用失败时安全 fallback；默认测试完全离线；秘密不进入日志、文档或提交。
- **必需测试：** 配置启用/缺失、请求结构与超时、模型与输出提取、错误映射、空响应、默认应用真实接线、fallback 健康状态。
