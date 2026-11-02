# Company Intelligence 阶段交付

## 检查与开发计划

现有 Product / Source / Snapshot / Claim、DeepSeek Provider、受控任务和 Vue 工程全部保留。旧 Source 原先强制属于 Product，不能表达企业文章；旧 Claim 描述能力，不能代替一次可确定的进展事件。本阶段以增量迁移 003 扩展，不将旧 Claim 强行转为进展。

实施顺序：数据库增量迁移 → 多源适配器 → 单主研究策略的多事件结构化提取 → 企业 API / 五类页面 / 周报 → 离线回归及真实采集。未增加多 Agent 或调度系统。

## 数据设计

- Company 独立于 Product。旧 Product 的 company 文本保留，新增 company_id 外键。
- Project 独立存储企业项目和技术方向，一家公司可有多个 Product 和 Project。
- Source 的 product_id 可空，新增 company_id、project_id 和 evidence_authority；企业来源不需要虚构产品。
- Snapshot 和旧 Claim 原样保留。企业来源共享相同的正文归一化、SHA256 和相邻去重。
- ProgressEvent 包含 company_id、project_id、snapshot_id、event_type、title、description、capability_tags、progress_stage、published_at、occurred_at、evidence_ids、evidence_level、verification_status 及带单位 metrics。
- EventEvidence 保存原文引文、企业、快照、真实来源和证据等级；日期引用也在存在时保存。
- ProgressRun 单独记录每快照的事件提取状态、错误、用量。成功复用；失败可重试。
- ResearchTask 新增 task_kind，沿用单进程执行器、任务日志及重启恢复。

数据库迁移前通过 SQLite backup 保存 `backend/insightflow.before-company.db`（被 Git 忽略）。SQLite 批量重建表时临时关闭迁移连接外键，迁移后立即执行 foreign_key_check；应用连接继续开启外键。迁移 003 不提供自动降级，避免误删新研究历史。恢复备份前请关闭后端并另行保存新数据。

## 采集器

| 类型 | 实现与边界 |
| --- | --- |
| official_website / company_news / press_release / technical_blog / customer_case / industry_media / job_posting / other | 受限 HTTP + HTML 正文；需显式提供单页 URL，不自动爬完整站 |
| github | 官方 API 获取 repo、README 和最近 Release；兼容旧 github_repository 类型 |
| arxiv | 官方 Atom 元数据 API；若 robots 不允许 API，则仅尝试同样经 robots 检查允许的官方 abs 页 citation 元数据与摘要，不抓论文全文 |
| wechat_official_account | 手动提交 mp.weixin.qq.com/s 文章 URL，公开 js_content 正文提取；robots、验证码、删除或访问限制均停止 |
| video | 可登记来源，但不自动下载视频或转录，采集返回明确错误，请提供公开文字稿 |

arXiv、GitHub、公众号、通用网页有各自并发闸门；共享公网 DNS 固定、重定向校验、20 秒请求超时、2MB 上限、每请求至少 0.5 秒间隔和网络失败一次重试。arXiv 另加至少 3 秒请求间隔。HTTP 访问失败不会导致其他来源崩溃。

微信公众号 Provider 可替换：`register_wechat_provider(provider)` 接入具有 async search(query) 和 fetch(url) 的实现，禁止私有 Cookie 或后台 Token。

内置合规搜索网关适配：环境变量 WECHAT_SEARCH_API_URL、WECHAT_SEARCH_API_KEY；契约为 `GET ?q=...`，返回 `{results:[{title,url}]}`。只保留公开公众号文章域名结果，不自动抓取或采信搜索摘要。第三方接口必须有合法服务授权；用户需自行提供合规服务，未配置时明确报错。密钥仅用于该服务的 Bearer 身份认证，重定向不转发；不是公众号后台凭据。本阶段没有配置外部搜索服务，也未执行真实公众号文章验收。

## 提取与证据等级

一篇文章可返回多个事件；Pydantic 限定枚举、日期、列表和长度。关联企业由服务器给定，项目名称必须出现在快照中才能自动建档；未知项目为 null。每个事件必须有逐字匹配 Snapshot 的非空引文，失败候选丢弃并统计，不生成无证据的事件。

日期为来源明确日期（UTC 日期语义），未知为 null，前端显示 unknown。发布时间、实际发生时间和抓取时间彼此分开，不用抓取日期补齐未知。日期缺少引文或引文中的年月日不匹配时清空。阶段未知用 unknown；计划试点、预计部署、拟量产等被识别时保守降级，不当作已经完成。

数字及单位必须出现在对应逐字引文中，否则指标不保存。网页是纯文本不可信输入，不能执行其中的指令。

证据等级是**来源属性**，不由模型自由升级：普通新闻、企业官网和转载默认 company_claim；GitHub/arXiv 为 technical_artifact。管理员在添加来源时，只有已核对真正独立测试或客户作者确认的来源，才应明确选择 independent_verification 或 customer_confirmation。系统不能独立验证作者身份，所以这两类依赖人工审阅；未将它们自动推断为事实。

verification_status=verified 仅表示关联与原文匹配，并不证明企业自述为真，也不证明模型摘要与引文语义完全一致。阶段、事件类型和技术标签仍需研究员审阅；营销性技术突破声明不等于真正独立证实的突破。一个 pilot 事件不代表企业整体已商业化。暂不跨文章自动裁决冲突，不对公司计算“领先排名”。

## 初始档案和来源发现

初始化 Simate、NVIDIA、智元机器人、北京人形机器人创新中心、逐际动力、银河通用、Physical Intelligence、Figure AI、1X、宇树科技、优必选，共 11 家。身份档案不预填技术成果、阶段或日期。官网 URL 是待研究入口，不表示所有站点均已采集成功；分类默认待研究，可在企业档案中编辑。

已通过官方公开页面逐步发现 PI 技术博客、PI openpi GitHub、π0 arXiv 论文和逐际动力新闻页。页面读取工具对智元、银河官网曾超时；其档案来源保持 pending，不冒充抓取成功。没有把人工搜索摘要写进 Snapshot。

## 页面和操作

- `/companies` Company Intelligence：企业档案、分类、启停和添加多来源。
- `/companies/{id}` Company Profile：编辑资料、技术方向、产品/项目、来源状态、历史快照和事件时间线。
- `/feed` Intelligence Feed：按文章日期展示事件；未知日期保留为 unknown。支持企业、技术方向、阶段筛选。
- `/tracker` Progress Tracker：research / prototype / demonstration / pilot / commercial_deployment / scaled_production / unknown 分组展示事件，不给企业整体硬定阶段。
- `/industry` Industry Map：以已保存事件的技术标签交叉展示企业，空格显示证据不足；标签由模型提取，尚未做同义词标准化。
- 任一事件的证据入口查看引文、证据等级、来源 URL 和完整快照。
- 页面“生成最近一周行业报告”保存到现有 Reports，可直接预览和 Markdown 下载。

周报严格按已知文章发布时间筛选最近 7 天的 UTC 日期范围，排除未来日期；未知日期事件不强行纳入。没有匹配事件时明确说明资料不足，而不是说行业没有进展。

## 新 API

| 方法与路径 | 用途 |
| --- | --- |
| GET / POST /api/companies | 分页查看和创建企业 |
| GET / PATCH /api/companies/{id} | 企业档案和资料编辑、启停 |
| POST /api/projects | 添加企业项目 |
| POST /api/company-sources | 添加企业来源，可指定所属项目和人工审阅证据等级 |
| PATCH /api/company-sources/{id} | 修改 URL、类型、启停，历史快照不变 |
| GET /api/wechat/search?q= | 可配置的合规搜索 Provider |
| POST /api/sources/{id}/fetch | 复用采集任务，纯企业来源自动提取 ProgressEvent |
| POST /api/snapshots/{id}/progress | 对已保存快照执行企业进展提取 |
| GET /api/snapshots/{id}/progress-run | 提取状态、错误、用量 |
| GET /api/progress-events | company_id、tag、stage、offset、limit 筛选 |
| GET /api/event-evidence/{id} | 原始事件证据 |
| POST /api/industry-reports | 生成已保存事件的最近一周报告 |

Simate/NVIDIA 的原产品来源仍走旧 Claim 流程；如需分析企业事件，在其历史快照中点击“提取企业进展”。新建纯企业来源则采集后直接进入企业事件流程。

## 验证结果和限制

真实来源验收记录见 `company-acceptance.json`，所有正式数据由真实请求生成，无 Demo 混入。两篇文章首次 DeepSeek 请求共 2 次，消耗 2,863 + 1,340 = 4,203 tokens；重复执行均复用，当前验收 JSON 的 usage 为空表示未新增调用。供应商账单为计费依据。

- PI API beta 文章：成功保存 5,723 字符，提取 3 个事件，证据全部匹配。
- 逐际动力 COSA 0.5 更新页：轻量正文仅 57 字符（标题、分类、日期），提取 1 个更新事件，发展阶段保持 unknown，不补造技术细节。
- openpi：官方 GitHub API 成功，21,539 字符。
- arXiv π0：API 被 robots 禁止；经许可的官方摘要页成功，2,174 字符元数据和摘要。
- 迁移后原 3 个 Product 和 16 条 Claim 保留，Snapshot 共 7 条，foreign_key_check 返回 0 条异常。
- 真实数据库共 11 家企业、4 条 ProgressEvent；全部为 company_claim，不宣称独立证实。三条 PI 事件发布时间未知；逐际动力日期为 2026-07-15，均不属于本周。
- 周报 API 实际保存 Report #1，明确说明当前数据库没有本周已知发布日期事件，未虚构动态。
- 前端生产构建与 TypeScript 检查通过；前端代理企业列表、事件、周报接口和 `/companies` HTTP 200 已验证。没有浏览器自动化工具，未声称做过视觉和完整点击验收。

自动测试使用临时数据库、Fixture 和 Mock Provider，与真实数据隔离。覆盖多事件、去重、证据、日期未知、指标过滤、失败事务、未来计划、来源路由、公众号限制/搜索、arXiv 元数据与合法回退、企业 CRUD 和周报七天边界。最终结果：58 passed in 24.51s。

当前只支持手动任务触发，不含定时调度。新闻索引页不会自动追踪所有文章链接；需逐步导入文章 URL。技术标签筛选在 MVP 内存完成后分页，较大数据集需优化 JSON 索引。Evidence IDs 通过受控事务验证后存为 JSON 引用，目前没有关联表外键；应用没有证据删除接口。生产公开部署仍需鉴权、出网策略和审阅机制。未执行 Docker 镜像构建。

## 启动与测试

在 backend 执行：

```powershell
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.company_seed
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另一个终端在 frontend 执行 `npm run dev`。`scripts/start.ps1` 和 Docker 启动已包含企业 seed。

真实多源验收（会访问公网，已有提取成功则复用）：在 backend 执行 `../.venv/Scripts/python.exe ../scripts/accept_company.py`。

参考：[arXiv API 官方手册](https://info.arxiv.org/help/api/user-manual.html)、[PI 官方文章](https://www.pi.website/blog/api-beta)、[逐际动力官方更新](https://www.limxdynamics.com/zh/news/BK000065)。
