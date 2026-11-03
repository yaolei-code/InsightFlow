# InsightFlow

面向具身智能行业的企业情报工作台：发现公开资料、保存原始快照、提取企业进展与产品能力，并用可追溯证据支持研究。**Evidence First, Analysis Second.** 搜索摘要、企业宣传和模型推断都不自动成为已证实的事实。

本项目用于展示全栈工程、数据采集、受控 AI 研究流程与证据追溯设计。首次安装不会带入开发者的数据库或密钥，可先运行离线测试，再配置自己的公开数据源与模型。

## 当前功能

- 企业、项目与产品分离管理；企业别名及多个公开来源。
- Tavily 搜索发现、栏目/sitemap 链接发现、候选 URL 规范化与去重；可自动采集入库，人工标记可选。
- 官网、新闻/博客、GitHub、arXiv、用户导入公开微信公众号文章等来源适配；保存正文、URL、时间、Hash 和真实错误状态。
- 从真实 Snapshot 提取 Claim、ProgressEvent、技术标签、阶段与公开指标；Pydantic 校验和原文证据匹配；保留未知、冲突和发布限定。
- 自然语言研究首页、企业档案/时间线、行业动态、技术矩阵/局部关系图/企业列表、产品能力对比。
- 数据库优先的有预算研究流程、可追溯报告、企业/技术关注和关注简报；事件关联、重要性依据与可选审阅状态。

## 架构与目录

```text
Vue 3 / TypeScript / Vite / Element Plus / Pinia
                 ↓ 本地 HTTP API
FastAPI → 采集与搜索适配 → Snapshot → LLM 结构化提取 → 证据校验
                 ↓ SQLAlchemy / SQLite / Alembic
       Company / Project / Claim / ProgressEvent / Report
```

`backend/app` 包含 API、服务和适配器；`backend/alembic` 是增量迁移；`frontend/src` 是现有工作台；`fixtures` 和测试目录仅保存离线测试资料；`scripts` 是启动、审计及显式联网验收脚本。真实数据库与运行产物只在本地保留。

## 安装

需要 Python 3.11+（建议 3.12）、Node.js 22+ 和 npm。以下命令在项目根目录的 PowerShell 执行。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[test]'
# 仅在 .env 不存在时复制，避免覆盖已有密钥。
if (!(Test-Path .env)) { Copy-Item .env.example .env }
cd frontend
npm ci
cd ..
```

没有 Windows Python Launcher 时用 Python 3.11+ 的 `python`，或 `uv venv --python 3.12 .venv`。Linux/macOS 用 `.venv/bin/python`；手动启动时先进入 `backend`。

前端 `package-lock.json` 用于 `npm ci`；后端版本范围见 `backend/pyproject.toml`，开发环境版本记录见 `backend/requirements.lock`。若需复现该环境，可先用 `pip install -r backend/requirements.lock`，再安装本地项目。

## 配置

复制后的 `.env` **只在本地编辑，不提交**。完整无密钥模板见 [.env.example](.env.example)。系统按根目录绝对路径加载 `.env`，进程环境变量优先。

| 变量 | 用途与默认值 |
| --- | --- |
| `DATABASE_URL` | `sqlite:///./insightflow.db`；相对后端工作目录 |
| `OPENAI_API_KEY` | 模型密钥；空值时明确报告模型未配置 |
| `OPENAI_BASE_URL` | 空值使用官方 OpenAI 端点，可配置兼容服务 |
| `OPENAI_MODEL` | 默认 `gpt-4.1-mini`，须是账户可用模型 |
| `LLM_PROTOCOL` | `responses`、`chat`、`json`；兼容端点可用 JSON 模式，仍校验结构 |
| `ENABLE_TRACING` | 默认 `false`；开启会向 SDK 的追踪服务发送研究内容 |
| `TAVILY_API_KEY` | Tavily 公开网页搜索；缺失时报错，无虚假搜索结果 |
| `SEARCH_PROVIDER` | `tavily`（默认）或 `github` |
| `GITHUB_TOKEN` | 可选，GitHub API Token；不是仓库推送认证配置 |
| `WECHAT_SEARCH_API_URL` / `WECHAT_SEARCH_API_KEY` | 可选合规第三方搜索接口，约定见模板 |
| `AUTO_INGEST_DISCOVERIES` | 默认 `true`，自动采集已发现候选正文 |

DeepSeek 兼容配置示例（密钥仍只在 `.env` 本地填写）：

```dotenv
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-flash
LLM_PROTOCOL=json
ENABLE_TRACING=false
```

没有配置模型或搜索密钥时仍可浏览已有数据；相应 AI/搜索操作会提示配置缺失。真实请求失败会保留错误状态，不返回 Mock 研究结论。

## 初始化与运行

终端一，从项目根目录执行：

```powershell
.\scripts\start.ps1
```

脚本执行迁移、幂等种子初始化，并启动后端。手动等价步骤：

```powershell
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.seed
..\.venv\Scripts\python.exe -m app.company_seed
..\.venv\Scripts\python.exe -m app.discovery_seed
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

终端二：

```powershell
cd frontend
npm run dev
```

访问 [工作台](http://127.0.0.1:5173) 和 [API 文档](http://127.0.0.1:8000/docs)。初始种子不含已采集正文；新安装不会自动拥有开发机器中的事件、报告或数据库。修改配置后重启后端。已有数据库升级前自行备份，不要删除数据库来替代迁移。

Docker 可通过根目录 `docker compose up --build` 启动，访问端口 8080；SQLite 使用命名卷。本次整理未执行 Docker 构建。

## 测试

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
cd ../frontend
npm test
npm run build
```

后端测试使用本地 Fixture、临时数据库和 Mock Provider，不需要公网或真实密钥；前端规则测试同样离线。Mock 不写入正式研究库。评测可从根目录执行 `.\.venv\Scripts\python.exe evals/run.py`。

`frontend/tests/workspace.e2e.mjs` 和 `scripts/accept_*.py` 等验收脚本是**显式联网**流程：需要运行中的服务、可用模型/搜索配置，可能收费且写入真实数据库，不属于普通离线测试。浏览器验收还需要本机 Edge。历史验收文档仅代表对应日期结果；本次实际测试与上传检查见 [GitHub 准备记录](docs/github-readiness.md)。

## 数据安全与 GitHub 上传

- `.env`、密钥文件、数据库及日志、缓存、虚拟环境、构建和运行产物均应保持本地；模板只使用空密钥。
- `.gitignore` 不能移除已经跟踪的文件，也不能清除历史对象。提交前运行 `.\.venv\Scripts\python.exe scripts/audit_repository.py`，该脚本输出位置和类别，不输出匹配值。
- 维护者已确认公开展示，并接受历史中的5份真实运行 JSON。它们不含已发现的真实凭据；当前版本不再跟踪这些产物，历史仍完整保留。检查范围见 [准备记录](docs/github-readiness.md)。
- 保留既有提交历史。不得通过重新初始化、强制推送或未确认的历史清理绕过检查。

## 已知限制

- 当前是本地可信用户、单实例工作台，没有完整多用户认证、授权及公网部署防护。服务应只绑定回环地址。
- HTTP 采集不执行 JavaScript，不绕过登录、验证码、Cookie 或访问限制；动态正文、robots 和网络限制可能造成资料缺口。
- 搜索结果必须取得正文和快照才能生成正式证据。没有结果表示当前资料不足，不能推断行业没有进展。
- 原文匹配不证明企业声明为真，也不等于独立验证；演示、规划、试点、商业化和量产需要分别查看证据。
- 事件关联和重要性是保守辅助规则，可能漏合或误判；分数不是真实性概率或商业估值。
- 研究有工具与内容预算，不保证解答所有开放问题；不提供复杂 Multi-Agent、生产任务队列或自动定时发送。
- 前端包体积、分页、动态来源覆盖和真实标注集仍有改进空间。

更多设计见 [架构](docs/architecture.md)、[API](docs/api.md)、[企业情报](docs/company-intelligence.md) 和 [覆盖扩展](docs/coverage-expansion.md)。
