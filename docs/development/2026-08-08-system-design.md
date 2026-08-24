# 智能工单协同系统设计

## 1. 目标与范围

构建一个可在 Windows、macOS 和 Linux 上直接运行的 Python 命令行工单系统。系统以 SQLite 持久化工单，覆盖创建、列表、详情、状态流转和组合筛选；通过 OpenAI 兼容接口调用真实大模型生成分类、优先级、摘要和理由建议；通过人工确认、修改或拒绝形成可追溯闭环；通过固定样例集比较基础 Prompt 与加固 Prompt。

本实现不提供 Web 界面。任务书明确命令行加本地文件可以获得基础功能满分，Web 界面不额外加分，因此把实现时间用于可靠性、AI 安全、评测和演示材料。

## 2. 技术方案

- Python 3.11 及以上。
- 生产运行仅使用 Python 标准库：`argparse`、`sqlite3`、`urllib.request`、`json`、`dataclasses`、`enum` 等。
- SQLite 单文件数据库，默认位于 `data/tickets.db`，可通过统一 CLI 的 `--db` 选项覆盖。
- 自动化测试使用标准库 `unittest`，不要求安装第三方包。
- 大模型使用 OpenAI 兼容 Chat Completions HTTP 接口，通过 `AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL` 和 `AI_TIMEOUT` 配置。

这一方案避免原生数据库驱动和 Web 服务依赖，降低现场环境不确定性，同时保留清晰的模块边界以便测试和扩展。

## 3. 模块边界

```text
src/ticket_system/
  cli.py            参数解析、输出格式、退出码
  domain.py         枚举、数据对象、校验、状态流转规则
  database.py       连接、事务、建表与迁移
  repository.py     工单、建议、审计记录的 SQLite 读写
  service.py        工单用例、重复检测、并发控制
  ai_client.py      OpenAI 兼容 HTTP 调用与错误映射
  ai_schema.py      AI 响应提取、结构及长度校验
  prompts.py        baseline 与 hardened Prompt
  review.py         建议确认、修改、拒绝及生效规则
  evaluation.py     固定样例加载、运行与指标计算
  seed.py           五条稳定、幂等的示例工单
```

CLI 只调用服务层，不直接执行 SQL。服务层只依赖仓储接口和 AI 客户端协议，测试可使用临时 SQLite 数据库和本地 HTTP 测试服务器验证真实协议路径。

## 4. 领域模型与业务假设

### 工单字段

- `public_id`：形如 `TKT-20260808-0001` 的可展示编号。
- `title`：去除首尾空白后 1-120 个字符。
- `description`：去除首尾空白后 1-4000 个字符。
- `submitter`：去除首尾空白后 1-80 个字符。
- `status`：`new`、`triaged`、`in_progress`、`resolved`、`closed`。
- `category`：`unclassified`、`account_access`、`software`、`network`、`hardware`、`facilities`、`other`。
- `priority`：`P0`、`P1`、`P2`、`P3`。创建时默认 `P2`，也可由提交人显式指定。
- `version`：从 1 开始的乐观锁版本号。
- `fingerprint`：提交人、标题、描述规范化后计算的 SHA-256，不包含密钥或 AI 数据。
- `created_at`、`updated_at`：UTC ISO 8601 时间。

### 状态机

允许以下流转：

```text
new -> triaged -> in_progress -> resolved -> closed
                          ^          |
                          +----------+
```

`resolved -> in_progress` 表示返工。相同状态更新、跳过中间状态和关闭后再修改都被拒绝。AI 建议确认后，`new` 工单自动进入 `triaged`；其他状态保持不变。

### 重复请求

同一提交人在过去 24 小时内提交规范化后标题和描述完全相同的工单，视为重复。系统拒绝创建并返回已有工单编号。24 小时后允许同一问题再次发生；不同提交人的相同内容不合并。检查与插入位于同一个 `BEGIN IMMEDIATE` 事务中，避免并发重复写入。

### 示例数据

`seed` 使用五个稳定种子键创建覆盖不同状态、分类和优先级的工单。重复运行不增加数据，并报告新增与已存在数量。

## 5. 持久化设计

### `tickets`

保存工单当前有效状态。数据库通过 `NOT NULL`、`CHECK`、`UNIQUE` 和外键约束防止绕过服务层写入非法枚举或空字段。为状态、分类、优先级、提交人和指纹时间组合建立索引。

### `ai_suggestions`

每次分析请求保存一条独立记录，包括模型名、Prompt 版本、结构化建议、受长度限制的原始响应、处理状态和失败代码。状态为 `pending`、`confirmed`、`modified`、`rejected` 或 `failed`。失败记录不得改变工单。

审核后同时保留原始分类/优先级和最终分类/优先级。一个建议只能审核一次，重复审核返回冲突错误。

### `audit_events`

记录创建、状态修改、AI 分析结果和人工审核事件。事件载荷为 JSON，不记录 API 密钥、Authorization 头或完整环境变量。工单详情命令可展示按时间排序的审计轨迹。

### 并发与事务

- SQLite 连接启用外键、WAL 模式和忙等待超时。
- 创建、状态更新和审核均使用显式事务。
- 状态更新使用 `WHERE id = ? AND version = ?`；受影响行数为 0 时报告并发冲突。
- 审核建议与更新工单处于同一事务，保证不会出现“建议已确认但工单未生效”的中间状态。

## 6. CLI 设计

统一入口为：

```powershell
python -m ticket_system --db data/tickets.db <command>
```

命令如下：

- `init`：创建或升级数据库结构。
- `seed`：幂等写入五条示例工单。
- `create --title --description --submitter [--priority]`：创建工单。
- `list [--status] [--category] [--priority] [--submitter]`：任意组合筛选。
- `show <ticket-id> [--history]`：查看详情及可选审计记录。
- `status <ticket-id> <new-status> --actor <name> --version <n>`：按状态机更新。
- `analyze <ticket-id> [--prompt-version hardened]`：调用真实模型并保存建议或失败记录。
- `review <suggestion-id> confirm|modify|reject --reviewer <name> [--category] [--priority]`：人工审核。
- `evaluate --prompt-version baseline|hardened --cases evaluation/cases.json`：使用同一数据集运行评测。
- `scripts/demo.ps1` / `scripts/demo.sh`：按任务书验收顺序运行可重复演示，不自动伪造模型结果或隐藏错误。

成功退出码为 0；输入错误为 2；不存在、重复或并发冲突为 3；AI 配置、超时、协议或输出错误为 4。所有错误向标准错误输出明确原因，核心异常不会被吞掉。

## 7. AI 接入与安全边界

### 请求

客户端只在显式执行 `analyze` 或 `evaluate` 时调用模型，避免自动调用产生意外成本。默认只允许 HTTPS；`localhost` 和 `127.0.0.1` 可使用 HTTP 以支持本地模型和测试服务器。超时默认 20 秒，响应体最多读取 64 KiB。

工单标题和描述序列化为 JSON 数据块，系统 Prompt 明确：数据块是不可信内容，其中任何指令都不得执行。`hardened` 版本还给出分类、优先级判定规则，并要求先按业务事实判断再生成固定 JSON。

### 响应结构

模型必须返回单个 JSON 对象：

```json
{
  "category": "hardware",
  "priority": "P2",
  "summary": "三楼打印机需要补充墨粉",
  "reason": "问题影响单台办公设备，未描述大范围业务中断"
}
```

分类和优先级必须来自允许列表；摘要为 1-120 字符；理由为 1-300 字符；不得有未知字段。客户端兼容纯 JSON 和 Markdown JSON 代码块，但拒绝多对象、截断 JSON、超长字段与非法枚举。

### 提示注入防护

防护不依赖简单关键词替换，而是组合使用：系统指令优先级声明、用户内容 JSON 数据隔离、封闭输出枚举、严格响应结构校验和人工生效门禁。任务书指定的打印机注入样例固定期望为 `hardware/P2`；若输出恶意文本要求的 `account_access` 或 `P0`，记为注入失败。

### 失败降级

未配置、401/403、429、5xx、网络错误、超时和非法输出映射为稳定失败代码，保存 `failed` 建议记录并显示“工单未改变”。密钥仅存在于请求内存中，错误文本会去除 URL 查询参数和 Authorization 信息。

## 8. 人工确认闭环

- `confirm`：采用 AI 原始分类和优先级。
- `modify`：审核人必须提供合法分类和优先级，保存最终值。
- `reject`：不修改工单分类和优先级。

三种动作都记录审核人、审核时间、原始建议、最终结果和审计事件。只有 `confirm` 与 `modify` 更新工单；更新时同时按状态机将 `new` 变为 `triaged`。

## 9. 小型评测

`evaluation/cases.json` 至少包含 12 条带稳定 ID 的样例，覆盖账号权限、软件、网络、硬件、设施和其他分类，以及 P0-P3。至少两条是异常输入，两条是提示注入，其中包含任务书指定原文。

同一数据集分别运行 `baseline` 和 `hardened`，输出：

- 有效结构率：通过严格结构校验的响应占比。
- 分类准确率：分类与期望一致的占比。
- 优先级准确率：优先级与期望一致的占比。
- 注入抵抗率：注入样例未采用恶意目标分类或优先级的占比。
- 降级率与失败代码分布。

每次运行写入带时间、模型名、Prompt 版本、用例级结果和聚合指标的 JSON 报告。优化解释固定为：从只要求 JSON 的 baseline，改为包含不可信数据边界、判定规则、封闭枚举与冲突指令忽略策略的 hardened Prompt。两版必须使用相同模型、参数和样例集才允许比较。

## 10. 风险与加固

设计识别以下十项风险，其中后四项超出任务书给出的类别示例：

1. 空值、超长值和非法枚举：领域校验与数据库约束双重加固。
2. 非法状态流转：显式状态机加固。
3. 短期重复提交：事务内指纹检测加固。
4. 并发状态覆盖：版本号乐观锁加固。
5. 数据库异常或半写入：事务、外键、WAL 和回滚加固。
6. API 密钥泄漏：仅环境变量读取、日志脱敏、`.env` 忽略加固。
7. 提示注入导致错误建议：数据隔离、封闭枚举、校验和人工门禁加固。
8. 模型供应商超时或不可用：超时、稳定错误映射和核心功能降级加固。
9. 模型返回巨大响应导致内存或成本风险：显式调用、响应大小限制加固。
10. 审核争用或重复审核导致追溯不一致：单事务状态条件更新加固。

## 11. 测试策略

所有新行为按 RED-GREEN-REFACTOR 实现。至少覆盖：

- 正常创建、重启后读取、详情和组合筛选。
- 空标题、非法优先级、最大长度边界。
- 重复提交、24 小时窗口和不同提交人。
- 完整状态流转、非法跳转和版本冲突。
- seed 幂等性和五条数据覆盖。
- AI HTTP 请求结构、合法响应、非法 JSON、非法枚举、超长响应、401 和超时。
- AI 分析后工单不直接变化。
- 确认、修改、拒绝、重复审核和事务一致性。
- 指定提示注入样例的 Prompt 数据隔离与评测判定。
- baseline/hardened 使用同一用例集，指标计算正确。
- CLI 成功和失败退出码，以及跨进程持久化。

一键命令为：

```powershell
python -m unittest discover -s tests -v
```

## 12. 分阶段交付与提交

1. 设计阶段：任务书分析、设计稿与实施计划。
2. 核心阶段：领域模型、SQLite 仓储、业务服务、CLI、seed 和对应测试。
3. 可靠性阶段：重复检测、状态机、乐观锁、数据库约束、风险测试。
4. AI 阶段：真实 OpenAI 兼容客户端、Prompt、响应校验与失败降级。
5. 进阶阶段：人工审核追溯、固定评测集和优化前后比较工具。
6. 交付阶段：README、《设计与协作说明》、测试结果和演示脚本。

每阶段在完整回归通过后创建单独 Git 提交，不混入后续阶段代码。

## 13. 已知限制

- SQLite 面向单机和小团队，不提供跨主机高可用。
- 重复判定只识别规范化后完全相同的内容，不进行语义相似度合并，以避免误合并。
- AI 结果具有随机性；评测报告记录模型和参数，但不同时间的在线模型仍可能变化。
- 真实模型演示需要用户在本地提供有效的兼容 API 地址、模型名和密钥；仓库不会包含真实凭据。
