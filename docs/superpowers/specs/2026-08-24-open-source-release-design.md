# 智能工单协同系统开源发布设计

## 目标与成功标准

把现有 Python CLI 工单系统整理为 `Meow-saucee/intelligent-ticket-system` 公开仓库，并将原始开发底稿保存到独立的 `Meow-saucee/intelligent-ticket-system-notes` 私有仓库。

发布完成必须同时满足：

- 公开仓库使用 MIT License，默认分支为 `main`，历史保持小步演进且不暴露本机路径、真实凭据或原始底稿。
- 私有 notes 仓库只保存 `findings.md`、`progress.md`、`task_plan.md` 及其历史，未登录访问者无法读取。
- README、打包元数据、贡献和安全文档准确描述当前实现，不宣称尚未实现的 Web UI、身份认证、授权或生产级保障。
- 本地测试、公开历史清理后的测试和 GitHub Actions 均通过；已有 Moonshot 评测的预测与指标在脱敏前后保持一致。
- 不安装 GitHub CLI；通过 GitHub 网页、原生 Git、HTTPS 和 Git Credential Manager 完成建仓、认证、推送与远程核验。

## 仓库、历史与署名

### 公开仓库

- 名称：`Meow-saucee/intelligent-ticket-system`。
- 可见性：public。
- 默认分支：`main`。
- 分发包名与命令保持 `ticket-system`，版本保持 `0.1.0`；本次不发布到 PyPI。
- GitHub 简介使用：`Local-first Python CLI ticket system with SQLite persistence, human-reviewed AI triage, audit trails, and prompt-injection evaluation.`
- Topics 使用：`python`、`sqlite`、`cli`、`ticket-system`、`ai-triage`、`human-in-the-loop`、`prompt-injection`、`llm-evaluation`。

### 私有底稿仓库

- 名称：`Meow-saucee/intelligent-ticket-system-notes`。
- 可见性：private。
- 从原仓库中筛选出三份底稿的历史，并增加一个仅在私有仓库存在的最终检查点提交，以保存当前未提交版本。
- 不在公开 README、Git submodule、仓库描述或链接中暴露该仓库。
- `HANDOFF.md` 是本地恢复文件，不属于公开交付物，也不进入任一远程仓库；通过本地 Git exclude 保留。

### 历史清理

- 保留现有 27 个提交及后续开源整理提交的顺序、提交信息、时间和既有署名，不做 squash。
- 公开历史的所有版本都移除 `findings.md`、`progress.md`、`task_plan.md`。
- 公开历史的所有 blob 都将真实用户目录替换为通用项目路径；最终文档使用相对路径或 `<project-directory>`，不再硬编码个人目录。
- 历史清理使用临时虚拟环境中的 `git-filter-repo`。先在新鲜隔离克隆中演练，确认没有提交被意外丢弃后，才在正式仓库应用同一规则。
- 正式改写前创建本地 Git bundle，并先完成私有 notes 推送；两者均可用于恢复。
- 改写后重新扫描全部可达对象，而不是只扫描工作树。

### 提交署名

- 既有提交继续保留 `Codex <codex@local>`，真实反映原始 AI Coding 过程。
- 新的设计、开源整理和修复提交使用仓库级配置：`Meow-saucee <116954433+Meow-saucee@users.noreply.github.com>`。
- README 明确说明项目由 `Meow-saucee` 主导并借助 Codex 完成，不把 AI 协作隐藏为纯人工开发。

## 公开内容设计

### README 信息架构

README 以中文为主，标题下提供一段简短英文简介，并按以下顺序组织：

1. 项目定位与三枚以内的 CI、Python、MIT 徽章。
2. 核心能力：SQLite 持久化、状态机、重复检测、乐观锁、AI 失败降级、人工生效门禁、审计追溯与提示注入评测。
3. 一张最多八个核心节点的 Mermaid 流程图，展示“创建工单 → AI pending 建议 → 人工确认/修改/拒绝 → 工单与审计更新”。
4. 60 秒快速开始，同时给出 PowerShell 与 POSIX 命令。
5. 一段由真实程序输出整理的 CLI 示例，不制作或虚构 Web 界面截图。
6. AI 配置、数据流向和隐私边界。
7. 测试、评测证据与可重复命令。
8. 项目结构、已知限制、相关文档、贡献方式、许可证与 AI 协作说明。

README 不使用“企业级”“生产就绪”“权限防越权”等超出现有证据的措辞。模型建议的具体分类与优先级作为评测目标和一次运行结果，不作为所有供应商或未来运行的稳定承诺。

### 开源元数据与社区文件

- 添加根目录 `LICENSE`，内容为标准 MIT License，版权行使用 `Copyright (c) 2026 Meow-saucee`。
- 添加 `CONTRIBUTING.md`，说明开发环境、测试命令、提交范围、禁止提交密钥以及 AI 行为变更必须附评测或测试证据。
- 添加 `SECURITY.md`，要求通过 GitHub Security Advisory 私下报告漏洞，不公布个人邮箱或承诺固定响应 SLA；仓库设置中启用 private vulnerability reporting。
- 添加 `.gitattributes`，统一文本行尾，并强制 `*.sh` 使用 LF。
- 扩充 `.gitignore`，覆盖 `.env.*`、根目录数据库、`*.sqlite*`、证书/私钥、凭据目录、测试缓存、覆盖率、构建产物、日志、IDE 文件和生成报告；示例配置文件需要用显式否定规则保留。
- 完善 `pyproject.toml` 的 description、readme、license file、作者、keywords、classifiers 和项目 URL；不增加运行时依赖。

### 文档与评测证据

- 将正式规格和实施计划整理到 `docs/development/`，保留系统设计、实施计划和本开源发布设计，不公开原始三份工作日志。
- 更新 `docs/设计与协作说明.md`：把“越权”修正为“未经审核不得生效”，明确 actor/reviewer 只是审计标签，不是认证身份。
- 更新 `docs/验收演示步骤.md`：使用可移植路径，区分稳定验收规则与一次模型运行结果。
- 更新 `docs/test-results.md`：记录运行环境、提交标识、样例哈希、指标含义和脱敏报告链接。
- 从本地忽略目录中只选取最终 baseline 与 hardened 结果，生成：
  - `evaluation/results/moonshot-v1-8k/2026-08-09-baseline.json`
  - `evaluation/results/moonshot-v1-8k/2026-08-09-hardened.json`
- 公开报告保留模型名、日期、Prompt 版本、样例 SHA-256、每例 ID、期望值、预测分类、预测优先级、稳定错误码和聚合指标；移除密钥、HTTP 头、完整 HTTP 报文、完整原始模型响应、本机路径、用户名和无关本地配置。

## 行为修复与持续集成

### PowerShell 演示失败传播

`scripts/demo.ps1` 对每次原生 Python 调用显式检查 `$LASTEXITCODE`。需要 JSON 的命令先捕获输出、检查退出码，再解析 JSON；预期失败场景继续单独校验退出码。任一非预期失败都立即终止脚本并返回非零状态，成功路径的业务输出保持不变。

增加 Windows 回归测试：临时把一个固定返回非零码的 `python.cmd` 放到 PATH 前端，运行 PowerShell 演示并断言脚本返回非零。POSIX 脚本继续依靠 `set -euo pipefail`，并在 Ubuntu CI 中真实运行。

README 准确区分：自动演示覆盖核心流程、非法输入、重复、可选真实 AI 和测试；模型供应商失败的完整人工步骤与自动化协议测试分别由验收文档和测试套件提供。

### GitHub Actions

添加 `.github/workflows/ci.yml`：

- 触发条件为推送到 `main` 和针对 `main` 的 pull request。
- 权限最小化为 `contents: read`。
- 使用官方 `actions/checkout@v7` 与 `actions/setup-python@v7`。
- 测试矩阵为 `windows-latest`、`ubuntu-latest` × Python `3.11`、`3.12`、`3.13`、`3.14`。
- 每个矩阵任务执行隔离安装、`python -m unittest discover -s tests -v` 和 `python -m compileall -q src tests`。
- 在每个操作系统的 Python 3.14 任务中额外运行无密钥演示脚本；环境显式清除 `AI_API_KEY`、`AI_MODEL` 和 `AI_BASE_URL`，不会产生真实 API 调用或费用。

## 脱敏等价性

脱敏是证据转换，不是重新评测或改写结论。以下字段必须逐例相等：case ID、期望分类/优先级、预测分类/优先级、成功或稳定错误码。由这些字段重新计算的有效结构率、分类准确率、优先级准确率、注入抵抗率和降级率必须与原报告一致。

当前 47 项既有测试必须全部继续通过；本次新增的 PowerShell、元数据、CI 和公开评测回归测试也必须通过。公开历史清理前后的完整测试数量与结果必须一致。允许变化的只有运行耗时、临时目录、绝对路径、Python/SQLite 补丁版本和测试输出顺序。PowerShell 演示在成功场景下保持等价，在非预期原生命令失败场景下由“可能假成功”变为可靠失败，这是本次唯一有意修改的执行行为。

若公开报告无法从保留字段重算出原指标，或任一预测发生变化，则不发布该报告并停止上线流程。

## 上线流程与恢复策略

1. 完成文档、元数据、测试和脚本修复，创建小步提交；运行全部本地验证。
2. 从原仓库隔离生成 notes-only 历史，加入三份底稿当前快照；在已登录 GitHub 网页创建空的 private notes 仓库，不初始化 README、License 或 `.gitignore`。
3. 使用 HTTPS 和 Git Credential Manager 推送 notes 仓库；通过已登录页面确认内容，通过未登录请求确认不可见。
4. 创建本地 Git bundle；在新鲜隔离克隆中演练公开历史过滤，核对提交数量、父子关系、文件树、署名、测试和敏感扫描。
5. 私有备份与演练均通过后，在正式仓库应用相同过滤规则，重命名当前分支为 `main`，并再次运行完整验证。
6. 在已登录 GitHub 网页确认头像和仓库所有者为 `Meow-saucee`，创建空的 public 仓库，不预先生成 README、License 或 `.gitignore`。
7. 为正式仓库添加唯一的 `origin` HTTPS remote，核对 URL 后推送 `main`；首次认证由 Git Credential Manager 打开浏览器完成 OAuth/2FA。
8. 在网页设置简介、topics、Issues 和 private vulnerability reporting，并核对默认分支、MIT 识别、README、Mermaid 与文档链接。
9. 在 Actions 网页等待所有 Windows/Ubuntu 任务结束；任一失败都先修复并重新验证，不宣称发布完成。
10. 用未登录访问确认公开仓库可读、私有 notes 仓库不可读；记录最终 URL、公开 HEAD 和 CI 结果。

本次不安装 GitHub CLI。若网页会话或 Git Credential Manager 认证失败，停止并保留当前状态；只有用户再次批准后才使用 GitHub CLI、PAT 或 SSH 等后备认证方式。

任何凭据疑似命中都会阻止推送。私有 notes 未验证前不改写正式历史；隔离演练未通过不触碰正式历史；公开仓库创建后若首次推送失败，将其暂时改为 private，避免留下不完整的公开项目。恢复优先使用本地 bundle，其次使用私有 notes 历史和改写前隔离克隆。

## 验收清单

- 公开仓库与私有 notes 仓库名称、所有者和可见性正确。
- 公开历史保留全部非底稿提交，三份底稿和真实用户目录在所有可达对象中均不可检出。
- 既有 Codex 署名保留，新提交关联 `Meow-saucee` 的 ID 型 noreply 邮箱。
- README、MIT、项目元数据、贡献与安全文档在 GitHub 正确渲染。
- 公布的逐例评测和聚合指标与本地原报告一致，且不含被禁止字段。
- 原有 47 项测试和本次新增测试全部通过，且历史过滤前后完整测试数量与结果一致；编译、安装、PowerShell/POSIX 演示和 `git diff --check` 通过。
- GitHub Actions 在 Windows/Ubuntu 与 Python 3.11–3.14 全部成功，且未配置或调用真实 AI 密钥。
- 公开仓库匿名可读，私有 notes 仓库匿名不可读。

## 本次不包含

- Web UI、Logo、GIF、完整英文 README、正式 GitHub Release、PyPI 发布。
- 身份认证、角色权限、加密存储、SLA、监控或生产部署承诺。
- branch protection、Projects、Wiki、Discussions 或自动发布流水线。
- 对模型未来输出或其他供应商的准确率承诺。

## 参考资料

- [GitHub：Creating a new repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)
- [GitHub：Adding locally hosted code to GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)
- [GitHub：Caching your GitHub credentials in Git](https://docs.github.com/en/get-started/git-basics/caching-your-github-credentials-in-git)
- [GitHub：Email addresses reference](https://docs.github.com/en/account-and-profile/reference/email-addresses-reference)
- [actions/setup-python](https://github.com/actions/setup-python)
- [actions/checkout](https://github.com/actions/checkout)
