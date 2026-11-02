# Industry Intelligence Coverage Expansion

## 范围与检查

本阶段解决“已知 URL 少、发现不足”，复用 Company / Source / Snapshot / ProgressEvent / DeepSeek 和既有任务。用户正文在第五项“多来源事件合”处截断；本阶段落实明确的来源库、统一搜索、候选审核和采集元数据。附件中的自主研究循环属于另一项更大升级，本阶段没有实现或假装实现它。也没有实现未经明确规格的事件自动合并。

## 数据库迁移

迁移 004 新增 discovery_seeds、company_aliases、source_candidates、discovery_runs。SourceCandidate 保存标题、规范化 URL、域名、类型、企业、发现 Provider / 查询 / 时间、原搜索日期、摘要、相关度、来源信任提示、审核状态和既有来源关联，discovery_history 保留最近 20 次重复发现记录。

Snapshot 新增 title、published_at、source_type、capture_status；未知值为 null，不从搜索摘要回填事实字段。正文 HTML 的实际标题和公开日期 meta 会纳入保存文本，便于原文核验。arXiv citation 元数据同样可解析。历史 Snapshot 不改写、不凭空回填缺失字段。迁移前备份 `backend/insightflow.before-coverage.db`，数据库和密钥不提交。

URL 规范化包含域名/协议校验、去 fragment、排序参数、删除常见跟踪参数。保留尾斜线、协议和实际路径，因为它们可能对应不同资源。候选 URL 唯一；再次发现不覆盖审核结论，只增加发现记录。相同 URL 对不同企业的报道仍需人工判断，本版候选只有一个 company_id，不是多企业归因系统。

## 搜索 Provider

Tavily 使用固定官方 `https://api.tavily.com/search` 端点，API Key 放在根目录 `.env` 的 TAVILY_API_KEY。SEARCH_PROVIDER 默认 tavily；UI 可显式选择。官方参考：[Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search)。

支持中英文查询、企业别名、关键词、日期起止、限定域名。既有公司与别名用于候选归属提示；多家公司同时命中时不自动猜归属。source_trust_level 只是来源类别提示，不代表事实被证实。相关度是确定性关键词启发式评分，不是校准的模型置信度。

统一函数：search_industry_news、search_company_updates、search_technology_updates、search_company_website、search_company_github、search_company_papers；底层接口是 async search(query,start_date,end_date,domains)。论文搜索由 Tavily 限定 arxiv.org，不假装拥有不受限制的 arXiv 搜索 API。GitHub 仓库搜索使用无需 Key 的公开官方 API，支持可选 GITHUB_TOKEN；它不等同于行业新闻搜索，日期过滤是仓库 pushed 时间，绝不填成新闻发布时间。

默认包含 19 个具身智能研究关键词。没有 Tavily 密钥时，任务明确保存 failed / 未配置；不自动降级为 Mock。Tavily 针对 429/502/503 最多重试一次，25 秒超时；API 状态错误只记录 HTTP 状态码，不打印厂商响应正文或密钥。每次最多 10 条结果；不会请求搜索引擎生成答案。

搜索平台的日期、标题、摘要都只属于候选元数据。Provider 日期过滤可能不完善，因此搜索日期不能作为事实时间；进入正文提取后仍需证据校验。

## 栏目与 sitemap

初始来源库为 5 个指定行业平台 + 11 家既有企业官方入口，共 16 条。允许继续添加新闻栏目或 sitemap URL。每次读取入口、根 sitemap，最多两个嵌套 sitemap；单次最多 4 个页面、60 条待处理链接。只保留同域及公开公众号、GitHub、arXiv 的相关链接，不无限递归。

沿用公网地址校验、DNS 固定、重定向安全检查、robots、大小、超时和限频。每个入口分别记录 success / partial / error、检查时间和失败详情。栏目成功而 sitemap 404/无法解析时为 partial；这不是“完整网站接入”。静态页面没有链接时不凭空生成文章；JS 数据、分页和深层栏目仍需专门适配或搜索补充。

## 审核边界

搜索/栏目 → SourceCandidate(pending) → 用户确认企业和类型 → approved / rejected。

批准只注册或复用正式 Source，不执行采集、不创建 Snapshot、不生成事件。用户再点击“采集正式来源”，才走已存在的受控任务：采集真实正文 → 保存 Snapshot → DeepSeek 提取 → 逐字证据验证 → ProgressEvent。

已批准的重复审核幂等；不支持通过“拒绝”反转已批准来源，需在来源管理单独停用。企业未知时不能批准。既有来源也会被识别，但候选仍保留 pending 供审阅。

公众号可手动导入 URL，也可通过 Tavily 限定 mp.weixin.qq.com 发现，随后进入同一候选审核链。正文仍由已有公开文章 Provider 解析；受限时保留候选标题、日期元数据和真实错误，不绕过验证。government 和 customer_announcement 来源可登记并通过通用正文适配器获取；不会仅因域名或来源类型就自动标记“客户确认”或“独立验证”。video 仍只登记，暂不下载或转录。

## 页面与 API

新增 `/coverage`，包括真实统计、搜索表单、候选审核与分页、手动导入、行业来源库和发现运行记录。点击正式来源采集后在已有 `/tasks` 看进度。

| API | 用途 |
| --- | --- |
| GET /api/coverage | 覆盖统计、Provider 是否配置、默认关键词 |
| GET / POST /api/discovery-seeds | 来源库列表和添加入口 |
| POST /api/discovery-seeds/{id}/discover | 异步栏目 / sitemap 发现，202 |
| POST /api/discovery/search | 异步搜索发现，202 |
| GET /api/discovery-runs, /api/discovery-runs/{id} | 状态、参数、安全错误和真实结果 |
| GET / POST /api/source-candidates | 分页筛选或手动导入公开文章 |
| PATCH /api/source-candidates/{id}/review | 人工批准或拒绝 |
| GET / POST /api/company-aliases | 企业别名管理 |

发现任务是独立单进程队列，避免重复并发；进程重启标记 interrupted。没有增加多 Agent，也没有自动定时任务。来源库查询仍为小规模全量列表；候选支持服务端分页。

## 真实验收（2026-11-02）

完整记录：`coverage-acceptance.json`，mock=false。

- 16 个入口全部实际检查：10 success、6 partial，最终没有未经检查的入口冒充成功。
- 机器人大讲堂、机器人新闻网：栏目可读，sitemap 失败。
- CDRA、具身纪、具身之家：在本次有限入口检查中可读取栏目 / sitemap，并发现候选；不代表全站覆盖。
- Simate 的无尾斜线 URL 首轮失败；修复规范化保留原路径后栏目可读，sitemap HTTP 404，最终 partial。
- NVIDIA、智元、1X：入口可读，但 sitemap 访问或解析失败，partial。
- 其余已登记企业入口在本次有限检查中 success。
- Tavily 3 次真实请求：中文行业查询 10 条、智元别名查询 10 条、限定官方域名的英文 VLA 技术查询 10 条；去重后分别新增 10 / 10 / 6 条候选。
- GitHub 公开 API 搜索 unitree：10 条仓库结果，新增 10 条候选。搜索结果并不保证仓库由宇树官方拥有，归属需要审核。
- 合计 **443 条去重候选，全部 pending**。正式来源 16、Snapshot 7、ProgressEvent 4，未把发现数量冒充事实数量或行业总量。
- 通过前端代理提交来源库 #12 的任务 #5 实际 completed：读取 2 页、发现 17 条链接、新增候选 0，验证重复发现去重。
- 前端 `/coverage` HTTP 200，统计、候选分页 API 返回真实数据库数据；已打开默认浏览器。无浏览器自动化工具，未声称完整视觉与点击验收。
- 前端 TypeScript 和生产构建通过。旧有产品/企业功能与新增离线测试共 **74 项通过（30.45s）**。
- 此次只有搜索 API 调用，没有新增 LLM 调用和进展事件。搜索费用以服务账户账单为准，未编造 token 或金额。

所有候选保留待审核，验收脚本不会自动批准。信息覆盖提升不等于事件验证数量已提升；下一步应由研究员审阅高相关候选并采集正文。本阶段未执行公众号、政府公告和客户公告的真实正文验收，也未执行 Docker 构建。

## 运行

在 backend 执行迁移和初始化：

```powershell
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m app.discovery_seed
..\.venv\Scripts\python.exe -m pytest -q
```

正常前后端启动见 README。`scripts/start.ps1` 和 Docker 已包含发现来源库 seed。

真实验收脚本：在 backend 执行 `../.venv/Scripts/python.exe ../scripts/accept_coverage.py`，会访问所有入口并消耗最多三次 Tavily 搜索请求。重复运行会更新真实状态和发现历史，候选去重；不要把测试计划的目标值当实测成绩。
