# 实际开发验证记录

日期：2026-11-02（Asia/Shanghai）。

| 阶段 | 实现 | 已执行验证 |
| --- | --- | --- |
| M1 | Python 3.12 虚拟环境、FastAPI、Vue/Vite、健康检查 | 安装成功；前端生产构建成功；TestClient 健康检查通过 |
| M2 | 实体、Alembic 初始迁移、CRUD、HTTP/GitHub、快照 | 迁移与 seed 成功；三个公开来源实际采集成功，建立真实基线 |
| M3 | 单主 Agent、结构化 Provider、原文验证、任务持久化 | SDK 0.24.0 实际安装并检查签名；无 Key 分支和 Mock 流程通过；真实 LLM 未运行 |
| M4 | 相邻版本 Diff、语义变化、影响分析 | 离线增删、时间噪声、版本回退、Mock 变化去重测试通过 |
| M5 | 七类工作台页面、API 接入、报告导出 | vue-tsc 和 Vite 生产构建通过；未执行浏览器视觉检查 |
| M6 | 测试、评测、Docker、文档 | 27 项 pytest 通过；离线评测成功；当前环境无 Docker 命令，镜像未构建 |

自动测试在 Windows 沙箱外以显式授权执行（沙箱下临时目录和 SQLite 文件操作受限）。最终结果：`27 passed in 10.75s`。后端 HTTP 健康检查和 Dashboard 已实际返回 200 / 正确统计。前端构建产物正常；Element Plus 等依赖导致主包较大，Vite 提示超过 500KB，尚未拆包优化。

真实采集日志：

- `https://mate-robot.cn/research/sinfra/` → success，建立基线。
- `https://github.com/FluxVLA/FluxVLA` → success，通过官方 API 获取说明、README 和最近公开 Release。
- `https://developer.nvidia.com/isaac` → success，建立基线。

上述结果写入本地 SQLite（数据库不提交）。没有密钥，不产生 AI Claim、竞争影响和语义变化；没有真实 LLM 测试或 Token 消耗。来源的变化记录数为零是正常基线结果。

离线评测：18 条标注组件样例，另加 3 条 Schema 样例。Diff precision/recall 为 1.0，证据校验分类正确率 1.0，输入候选证据通过率 0.625，Schema 验证器接受/拒绝正确率 1.0。真实 Claim Extraction Accuracy 为 null。具体样例和计算见 `evals/run.py`。这些小样本组件指标不代表模型的语义抽取或实际网页变化分析质量。

限制：未配置真实模型，无浏览器控制工具，无 Docker 引擎；这三项未验证，未将目标值当作实测成绩。

本地联调：前端 `http://127.0.0.1:5174/` 与经 Vite 代理的 `/api/products` 均实际返回 HTTP 200。默认沙箱内 5173 的网络访问受限，验证改为明确授权的本机进程。验证服务在交付前关闭，按 README 可重新启动。
