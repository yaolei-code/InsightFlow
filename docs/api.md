# REST API

启动后访问 `/docs` 获得完整参数与 Schema。错误统一为 `{"error":{"message":"…"}}`，验证错误额外含 fields。列表接口支持 offset、limit，产品相关列表支持 product_id。时间为 UTC ISO8601。

| 路径 | 方法 | 作用 |
| --- | --- | --- |
| /api/health | GET | 服务和模型配置状态，无密钥 |
| /api/dashboard | GET | 真实数据库统计和错误 |
| /api/products | GET / POST | 产品列表与创建 |
| /api/products/{id} | GET / PATCH / DELETE | 查看、编辑、软停用 |
| /api/sources | GET / POST | 来源列表与添加 |
| /api/sources/{id} | PATCH | 修改 URL、类型、启停 |
| /api/sources/{id}/fetch | POST | 单来源异步研究，202 |
| /api/sources/{id}/snapshots | GET | 历史快照 |
| /api/snapshots/{id} | GET | 原始保存正文 |
| /api/claims | GET | Claim 与证据引用（包含历史） |
| /api/changes | GET | 真实版本变化 |
| /api/impacts | GET | 已保存影响分析 |
| /api/research | POST | `{source_ids:[]}` 表示全部启用来源 |
| /api/tasks, /api/tasks/{id} | GET | 任务列表、状态、日志和用量 |
| /api/comparisons | GET / POST | 当前能力矩阵与人工审阅关系 |
| /api/reports | GET / POST | 列表或生成证据汇编，body 为 `{title: "标题"}` |
| /api/reports/{id} | GET | 冻结的 Markdown 和证据 ID |

创建资源返回 201，任务提交 202，普通读取与修改 200。无效输入 422，URL 安全或业务校验 400，不存在 404，任务占用 409。API 默认无跨源权限，Vite/nginx 同源代理，不向浏览器暴露环境变量。
