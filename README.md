# InsightFlow

积压全量处理已完成：443条候选中194完成、211跳过、38失败，未处理为0。行业地图现有398条来源事件记录、119个非空单元格；产品矩阵57条Claim中35条原文验证通过。记录数不代表去重新闻或独立能力数。[全量处理及矩阵修复](docs/backlog-and-matrix-fixes.md)。

**最新交互调整：无需人工审核。** 发现后自动采集正文、识别企业并提取带证据事件；现有积压可在 `/coverage` 一键处理10篇。人工登记仅作为可选操作。规则和实际结果见 [自动入库说明](docs/automatic-ingestion.md)。

最新 Milestone：**Industry Intelligence Coverage Expansion**。新增 `/coverage` 来源发现工作台，真实 Tavily / GitHub 搜索、16 个行业与企业入口、栏目 / sitemap 发现、公司别名和人工候选审核。实测 443 条待审核候选；正式进展仍为 4 条，未把搜索摘要当事实。实现与真实限制见 [覆盖扩展说明](docs/coverage-expansion.md)。

当前方向：**具身智能行业 Company Intelligence Platform**。新增企业档案、多源采集、多事件进展提取、企业时间线、行业技术地图和最近一周报告，保留全部产品研究功能。入口为 `/companies`；设计、迁移、实际验收与限制见 [企业情报阶段说明](docs/company-intelligence.md)。

企业阶段实测：11 家企业、4 条带真实引文的事件；官网新闻/技术博客、GitHub、arXiv 均已保存真实快照。公众号适配已实现并离线测试，尚无真实公众号验收文章。前端生产构建通过。

当前完整回归：**58 passed in 24.51s**（本地 Fixture / Mock Provider，含旧产品功能和新增企业功能）。

AI-Powered Competitive Intelligence & Product Change Analysis Platform

基于 AI Agent 的竞品情报监测与产品影响分析平台。**Evidence First, Analysis Second.**

第二阶段已接通 DeepSeek Flash 的真实快照提取：Sinfra 实测 16 条 Claim，11 条验证通过，5 条未知/待核验；43 项离线测试通过。配置、审计、限制及验收见 [第二阶段记录](docs/stage2.md)。

面向具身智能研发基础设施研究，初始对象为 Simate Sinfra、FluxVLA Engine、NVIDIA Isaac。产品不是完全等价的竞争对手，平台保留人工审阅的竞争关系，明确区分已发布、演示、计划、开发中和未知能力。

## 技术架构

Vue 3 + TypeScript + Vite + Element Plus + Pinia → FastAPI → SQLAlchemy 2 / SQLite。
受控研究工作流使用 OpenAI Agents SDK；确定性采集、规范化、Hash、Diff、数据库写入和证据校验在 Python 执行。Alembic 负责数据库迁移。

## 环境与安装

需要 Python 3.11+（建议 3.12）、Node 22+、npm。以下命令在项目根目录的 PowerShell 中执行。安装 uv 的用户可用 `uv venv --python 3.12 .venv` 替代第一条命令。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[test]'
Copy-Item .env.example .env
Set-Location frontend
npm ci
Set-Location ..
```

如果全局 Python 过旧，请明确调用 3.12 或使用 uv。当前开发环境已在 `.venv` 安装依赖。

## 初始化与启动

终端一（保持项目根目录）：

```powershell
.\scripts\start.ps1
```

等价手动命令：

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.seed
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

终端二：

```powershell
cd frontend
npm run dev
```

打开 [Web 工作台](http://127.0.0.1:5173) 和 [OpenAPI](http://127.0.0.1:8000/docs)。Linux/macOS 使用 `.venv/bin/python`，先进入 backend 再运行相同 Python 模块命令。

## 环境变量

根目录 `.env` 通过项目绝对路径定位，环境变量优先。后端仍建议在 backend 工作目录启动，保持相对数据库路径一致。

| 变量 | 用途 |
| --- | --- |
| DATABASE_URL | 默认 `sqlite:///./insightflow.db` |
| OPENAI_API_KEY | 可为空；为空仍可管理产品、抓取网页和导出证据汇编 |
| OPENAI_MODEL | 默认 `gpt-4.1-mini`，可换为账户可用模型 |
| OPENAI_BASE_URL | 留空使用官方端点 |
| LLM_PROTOCOL | `responses` 官方默认；`chat` 使用 SDK Chat Completions；`json` 为仅 JSON 模式的兼容端点适配，仍进行 Pydantic 校验 |
| ENABLE_TRACING | 默认 false；开启后 SDK Trace 会发送到 OpenAI，请自行审阅公开研究内容 |
| GITHUB_TOKEN | 可选，仅发送到 GitHub API，重定向不转发 |

兼容端点必须至少支持所选协议，无法保证所有供应商兼容。错误会写入任务状态，绝不替换为虚构结果。

## 测试与评测

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
cd ..
.\.venv\Scripts\python.exe evals/run.py
cd frontend
npm run build
```

测试不依赖公网或真实密钥。覆盖正文与噪声过滤、重复和回退快照、基线、功能增删、演示限定、缺失证据、冲突保留、恶意提示词、失败来源、API CRUD、SSRF 与 Schema。评测文件见 `evals/results.json`（本地生成）。Mock 仅用于测试，不进入真实研究数据库。真实模型准确率没有实际运行时为 null，不能用 Mock 成绩替代。

实际采集探针（会访问公网并写入真实数据库）：

```powershell
cd backend
..\.venv\Scripts\python.exe ../scripts/probe_sources.py
```

## 完整演示流程

1. 运行迁移与 seed，然后启动两个服务。总览应显示三个产品，尚未采集时成功率为「—」。
2. 在产品与数据源中查看或修改来源，开始研究；任务页查看进度、耗时和真实错误。
3. 进入产品详情查看历史快照。第一次只建立基线，不显示虚假的变化。
4. 无密钥时页面显示「未配置模型」。配置密钥后重启并再次研究，已有快照也可提取事实。
5. 在产品详情或能力矩阵点击 Claim，查看原文、URL、观察时间、限定状态及完整快照。
6. 再次采集相同内容，确认无重复快照或变化。真实网页变更后模型基于旧新快照分类，影响分析引用当前证据。
7. 离线可控变化演示：运行 `pytest tests/test_core.py::test_mock_model_change_pipeline -v`。它验证旧新版本及去重，完全隔离于产品数据库。
8. 选择至少两个产品，在对比页保存功能重叠、生态对标等关系。未知能力不会显示为不支持。
9. 生成报告，查看九个章节、原始证据引用，复制或下载 Markdown。报告是确定性证据汇编；模型推断以已保存的影响分析单独标记。

## Docker

```powershell
Copy-Item .env.example .env  # 已存在时跳过，避免覆盖配置
docker compose up --build
```

访问 [Docker Web](http://127.0.0.1:8080)。SQLite 使用命名卷。单实例、单 worker 运行，禁止扩展多副本共享进程内执行器。部署到公网前需要身份认证、授权、入口限流、出网策略和 HTTPS。

## 交付与限制

详细设计见 [架构](docs/architecture.md)、[API](docs/api.md)、[验证记录](docs/validation.md)。

- MVP 面向本地可信用户，不含登录系统。不要直接绑定公网。
- 自动化网页读取工具已确认三个初始 URL 可读；实际后端采集结果以来源状态为准，robots/网络限制不会被绕过。
- 轻量 HTTP 不执行 JavaScript；正文不足会报告错误，请使用可访问的公开文档源。未启用 Crawl4AI。
- 单进程工作流全局串行任务，最多两个并发 HTTP，2MB 上限、重试一次、每请求延迟至少 0.5s。严格遵守 robots，无法确认许可时不抓取。
- 证据验证表示原文匹配，不能证明语义蕴含或厂商描述真实。页面包含限定词时保守拒绝“正式发布”验证；跨来源矛盾保留供人工复核。
- Diff 只过滤空白、导航及显式更新时间行；复杂网页噪声仍需改进。无密钥时保留快照，不创建语义变化事件。
- 变化前后截取文本交给模型，超长资料的细节可能漏检；单来源 300 秒、单模型调用最多 3 turn / 4000 输出 token。Token 统计来自成功响应，不含供应商可能计费的失败请求，不估算货币费用。
- 当前 UI 各查询有条数上限（最多 200，报告/任务默认 50）；REST 支持 offset/limit，海量资料需增加前端翻页。
- 不提供定时监控、任务取消和复杂队列。重启将未完成任务标记 interrupted，可手动重试。
- 后续方向：动态页面适配、独立队列、多用户权限、冲突裁决与真实 LLM 标注集、分页 UI、报告对比。
