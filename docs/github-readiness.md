# 公开仓库上传准备检查

检查日期：2026-11-03（Asia/Shanghai）。维护者已明确选择公开用于面试展示，并接受历史中的5份真实运行记录。没有重新初始化、删除数据库或改写历史。尚未推送。

## 仓库与 Git

- 目标：`https://github.com/yaolei-code/InsightFlow.git`，**Public**，分支 **main**。
- GitHub连接器确认仓库存在，账号 `yaolei-code` 有管理和推送权限。只读 `git ls-remote --heads --tags` 成功、输出为空：检查时远程没有分支或标签。
- 整理前 HEAD `c918533`，11个提交，最早提交 `94a5614`。保留全部分支历史及本地reflog，不使用force/mirror。
- GitHub CLI 未安装；本地配置了 Git Credential Manager，但连接器授权不等于本机 Git 写入认证已验证。没有读取或输出凭据。本地 `origin` 配置为上述目标，仅修改本地配置，不向远程写入。
- 开始检查时已有10个文件变更。缺失的 `ReportPreview.vue` 已从 HEAD 补回，以修复3个页面的导入；其余5个服务文件、2个测试文件和验收文档删除保持本地原样，不混入整理提交。

## 安全扫描与数据范围

`scripts/audit_repository.py` 离线检查所有未忽略上传候选文件、分支和reflog涉及的历史blob，精确匹配本地配置的非空凭据，并检查常见Token、私钥、带凭据URL、疑似凭据赋值、私有地址和个人绝对路径。只输出类别、文件、行号和对象ID，不输出匹配原文。规则扫描不能证明不存在所有未知格式敏感信息。

初次扫描11个分支可达提交、187个历史blob，对2个本地已配置凭据做精确检查，没有发现真实凭据或实际内部服务地址。模式命中已人工核对：仅为测试中的SSRF拒绝样例和显式虚构脱敏测试字符串。已有Git作者姓名和邮箱属于提交元数据，保留不变。

以下文件包含实际运行统计、公开来源及错误、候选/事件ID、关注信息或研究摘要，没有发现真实凭据。**维护者已明确接受这些历史记录公开**：

- `docs/backlog-processing.json`
- `docs/company-acceptance.json`
- `docs/coverage-acceptance.json`
- `docs/stage2-acceptance.json`
- `docs/workspace-live-acceptance.json`

已使用 `git rm --cached` 停止跟踪这5份文件，本地文件完整保留。旧版本仍存在于完整历史中，普通推送会上传；新增忽略规则防止继续意外收录。

`backend/insightflow.db-shm` 仅在本地reflog旧对象中，不能从现有分支到达，普通推送main不会上传。现有分支树和分支历史未发现数据库文件。不得将整个目录或 `.git` 打包上传代替普通推送。

`.gitignore` 已覆盖派生 `.env`（保留空密钥模板）、常见密钥文件、数据库及sidecar、日志、data/snapshots/backups/exports/reports、缓存、虚拟环境、构建、覆盖率和浏览器验收产物。代表路径已验证。忽略规则不能代替对任意新文件的提交复查。

## 文档与验证

README已整理项目介绍、面试展示定位、当前功能、架构、安装、迁移/种子初始化、启动、完整环境变量、DeepSeek兼容配置、离线测试与显式联网验收区别、数据安全和已知限制。`.env.example` 仍只有空密钥，不复制本地 `.env`。

第一次针对原工作区验证：后端 **94 passed in 66.64s**，前端规则 **6 passed**；构建因为现有 `ReportPreview.vue` 删除而失败。未沿用旧的99项成绩冒充当前结果。随后补回组件，并对拟提交的索引导出进行独立回归，以避免本地未提交业务修改影响待发布提交的验证。

最终拟提交索引的独立回归：**99 passed in 77.53s**，前端规则 **6 passed**，TypeScript及Vite生产构建通过（18.51s）。主包约1.29MB，仍有超过500KB的提示。独立导出位于被忽略的 `.test-tmp/github-publish-tree`；这组结果对应拟公开版本，不能用来声称其余本地未提交业务修改也有99项通过。

提交前再次扫描191个历史blob（含Git暂存时写入的reflog可达树相关对象），本地配置凭据精确命中数为0；模式命中仍只有上述测试文件。完整脱敏报告为被忽略的 `.test-tmp/github-audit-public.json`。

没有运行真实采集、联网模型验收、迁移或Docker构建，没有修改正式数据库。

## 提交范围与上传确认

整理提交仅包括 `.gitignore`、`README.md`、本记录、`scripts/audit_repository.py` 和上述5份文件的索引删除。业务文件不夹带提交。消息：`chore: prepare public GitHub showcase and document security checks`。全部既有提交继续保留。

上传前需展示最终提交、Public、main、安全及测试结果，再等待维护者确认普通推送。不重复创建已有仓库，不强制推送。若本机Git写入认证不足，再使用正常的交互式登录，不能从连接器导出凭据。
