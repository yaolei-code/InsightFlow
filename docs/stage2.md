# 第二阶段：DeepSeek Flash 真实快照提取

## 工程检查结果

复用现有 Vue、FastAPI 和 SQLAlchemy 工程，没有重建项目。

| 检查项 | 原有实现 | 本阶段补齐 |
| --- | --- | --- |
| 数据模型 | 产品、来源、Snapshot、Claim、变化、影响、报告、任务 | 提取运行记录 extraction_runs；任务可引用保存的 Snapshot |
| 采集 | SSRF 校验、DNS 固定、robots、HTML/GitHub、大小和超时约束 | 保持原有行为 |
| Snapshot | SHA256、相邻去重、历史版本、来源 URL | 分析入口直接使用已保存内容，不要求再次访问网站 |
| Provider | 官方 Responses、SDK Chat、兼容 JSON | DeepSeek Flash JSON 路径、关闭思考、截断/空内容拒绝、安全错误、Schema 二次校验 |
| Evidence | Claim 内嵌引用，原文匹配 | Snapshot 存在、产品关联、保存 URL 一致、当前来源冲突检查 |
| API/前端 | 产品详情、原文抽屉、能力矩阵 | 快照提取按钮、采集时间、显式验证状态、任务日志；矩阵保留待核验/冲突标签 |

## 配置

根目录 `.env`（不入 Git；不要在聊天或命令行参数中发送密钥）：

```dotenv
OPENAI_API_KEY=填写你自己的密钥
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-flash
LLM_PROTOCOL=json
ENABLE_TRACING=false
```

官方 OpenAI 仍支持：BASE_URL 留空，MODEL 设为账户可用模型，PROTOCOL 使用 responses。
实际检查 SDK：openai 3.42.1、openai-agents 0.24.0；使用已安装的 AsyncOpenAI / chat.completions.create 接口。
JSON 模式不假定供应商支持严格 json_schema，返回内容经过 Pydantic 校验。仅对官方 api.deepseek.com JSON 请求添加 `thinking: disabled`，不向其他端点发送供应商专用参数。

配置现在以项目根路径定位，不再依赖启动工作目录；SQLite 相对路径仍以 backend 启动目录为准。

## 数据和安全规则

- 关联 ID、来源 URL 和观察时间由服务器从真实 Snapshot 赋值，模型不可指定。
- 未覆盖维度创建明确的 unknown/unverified 占位。无证据绝不标记 verified，也不推出 not_supported。
- 无效引用的候选保留供审阅，但状态降为 unknown/unverified。待核验候选的文字不是已证实事实。
- 演示、计划与开发状态保留；原页面出现限定词时，保守拒绝将模型的 released 判断直接通过。可能误伤同页面确实已发布的其他能力，需人工复核。
- 冲突识别是保守规则：同一产品的当前来源、同维度、同开放状态出现 supported 与 not_supported 时标为 conflicting。这是冲突候选，不是细粒度语义裁决。不同子能力可能造成误报，暂不自动裁决。
- 成功提取按 Snapshot 复用，包括无事实只产生未知的结果；失败允许重试；同批次重复候选去重；写入事务失败不残留半批 Claim。
- API 失败、超时、Schema 不符、空 JSON、截断均保存 failed。厂商响应正文及异常原始文字不进入任务日志，避免回显凭据。
- 页面文本作为不可信数据，不提供网页指令执行工具；这降低风险，但不能等同于证明模型免疫提示注入。

## 实际验收（2026-11-02）

使用已经保存的 Sinfra Snapshot #1，真实来源 `https://mate-robot.cn/research/sinfra/`。没有使用 Mock 代替模型输出。

| 指标 | 实测 |
| --- | --- |
| 模型 | deepseek-flash |
| 保存 Claim | 16 |
| 原文与关联验证通过 | 11 |
| unknown | 5 |
| conflicting | 0 |
| unverified | 5（与 unknown 重合，不相加） |
| 成功调用 | 1 次，4,212 tokens |
| 首次失败 | 输出未正常完成，达到 4,000 输出 token 限制；总消耗 6,655 tokens，未写 Claim |
| 两次真实调用合计 | 10,867 tokens；供应商账单为最终计费依据 |
| 离线自动测试 | 43 passed in 10.21s |
| 前端 | vue-tsc + Vite 生产构建通过 |

五条待核验的原因：一条引用不能逐字匹配快照；另四条引用可找到，但正式发布状态未通过保守限定词规则，均降级为 unknown/unverified。这些状态不代表产品不具备该功能。

真实验收结构化输出保存在 `stage2-acceptance.json`。重复提交 `/api/snapshots/1/extract` 的任务 #1 实际完成，复用 16 条记录，requests=0、tokens=0，没有重复模型调用和 Claim。

通过运行中的 Vite `/api` 代理核对：health 返回 model=deepseek-flash / configured=true；产品详情 Claims=16；比较 API Claims=16。详情页和比较页使用这些响应，已打开浏览器详情页。没有浏览器自动化工具，未声称做过视觉或点击验收。

## 使用

迁移：在 backend 执行 `../.venv/Scripts/python.exe -m alembic upgrade head`，保留现有数据。

在产品详情 → 历史快照 → 用已配置模型提取此快照。任务页查看完成统计；点击 Claim 打开证据抽屉。能力对比标明 verified / unverified / conflicting，不能将后两者作为已证实能力。

新增接口：

- `POST /api/snapshots/{id}/extract`：202，使用现有任务执行器分析快照；无模型 409。
- `GET /api/snapshots/{id}/extraction`：提取状态、错误、统计和用量；未执行返回 not_started。

命令行实际验收脚本：在 backend 执行 `../.venv/Scripts/python.exe ../scripts/accept_extraction.py`。成功后复用，不自动产生额外 API 费用。

本阶段只验收了 Sinfra 的事实提取到 UI API 数据链路；FluxVLA、Isaac 的真实 LLM 提取及跨产品语义影响分析仍未实际验收。没有增加多 Agent、调度或其他产品模块。

参考：[DeepSeek 接入](https://api-docs.deepseek.com/quick_start/agent_integrations/)、[JSON 模式](https://api-docs.deepseek.com/guides/json_mode/)、[思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)。
