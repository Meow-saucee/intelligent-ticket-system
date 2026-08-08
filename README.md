# 智能工单协同系统

这是一个 Python 3.11+ 标准库实现的命令行工单系统：SQLite 负责持久化，AI 通过 OpenAI 兼容 Chat Completions API 提供“建议”，人工审核后才会改变工单的有效分类和优先级。

## 快速开始

```powershell
$env:PYTHONPATH = "src"
python -m ticket_system --db data/tickets.db init
python -m ticket_system --db data/tickets.db seed
python -m ticket_system --db data/tickets.db list --status new --priority P1
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

生产代码只依赖 Python 标准库；可选地执行 `python -m pip install -e .` 后使用 `ticket-system` 命令。

## CLI 命令

```text
init
seed
create --title TITLE --description DESCRIPTION --submitter NAME [--priority P0|P1|P2|P3]
list [--status STATUS] [--category CATEGORY] [--priority P0|P1|P2|P3] [--submitter NAME]
show TKT-ID [--history]
status TKT-ID TARGET --actor NAME --version VERSION
analyze TKT-ID [--prompt-version baseline|hardened]
review SUGGESTION_ID confirm|modify|reject --reviewer NAME [--category CATEGORY --priority PRIORITY]
evaluate --prompt-version baseline|hardened --cases evaluation/cases.json --output-dir reports
```

状态流转为 `new -> triaged -> in_progress -> resolved -> closed`，`resolved` 可以返工到 `in_progress`。创建工单后，标题、描述和提交人会被规范化；同一提交人在 24 小时内提交相同内容会返回已有工单编号。

## AI 配置与安全边界

正式调用需要设置 `AI_API_KEY`、`AI_MODEL`，可选 `AI_BASE_URL`（默认为 `https://api.openai.com/v1`）和 `AI_TIMEOUT`。密钥不会写入数据库、审计事件或错误文本。建议先运行：

```powershell
$env:AI_API_KEY = "<your-key>"
$env:AI_MODEL = "<your-model>"
$env:AI_BASE_URL = "https://api.openai.com/v1"
python -m ticket_system --db data/tickets.db analyze TKT-...
```

系统严格校验模型 JSON，只接受六种分类和四种优先级；模型失败会保存 `failed` 建议，核心列表和详情命令仍可用。AI 结果初始状态为 `pending`，必须通过 `review` 的 `confirm`、`modify` 或 `reject` 才能形成最终结果。

## 演示与证据

任务书现场顺序由 `scripts/demo.ps1` 和 `scripts/demo.sh` 覆盖：正常生命周期、非法输入、重复提交、AI 建议、提示注入、模型失败降级和一键测试。没有有效 AI 配置时，脚本会明确跳过真实模型步骤，不伪造结果。

固定评测集为 `evaluation/cases.json`，包含 12 个正常、边界、异常和提示注入样例；可在有真实配置时分别运行 baseline 与 hardened：

```powershell
python -m ticket_system --db data/eval.db evaluate --prompt-version baseline --cases evaluation/cases.json --output-dir reports/baseline
python -m ticket_system --db data/eval.db evaluate --prompt-version hardened --cases evaluation/cases.json --output-dir reports/hardened
```

实现依据与风险清单见 [docs/设计与协作说明.md](docs/设计与协作说明.md)，实际验证记录见 [docs/test-results.md](docs/test-results.md)。

## 需求到证据

| 任务书要求 | 证据 |
|---|---|
| 创建、持久化、重启读取 | `tests/test_repository.py`、`tests/test_cli.py` |
| 列表、详情、双条件筛选 | CLI `list` 与 `test_create_list_and_show` |
| 状态修改与并发保护 | `tests/test_reliability.py` |
| 至少 5 条可复现样例 | `seed` 与 `test_seed_creates_five_stable_diverse_tickets` |
| 六项以上风险、三项以上加固 | 设计说明风险表及输入/重复/版本/密钥/注入/供应商失败实现 |
| 至少 6 个自动化测试 | 当前测试套件覆盖 45+ 个真实测试 |
| 真实模型、严格校验、失败降级 | `ai_client.py`、`ai_schema.py`、`analysis.py` 及 HTTP 测试 |
| 人工确认、修改、拒绝和追溯 | `review.py`、`tests/test_review.py`、`show --history` |
| 10+ 条评测和可解释优化 | `evaluation/cases.json`、baseline/hardened Prompt |
| 完整源码、测试结果和协作说明 | 本仓库源代码、本文档、`docs/`、`scripts/` |

## Git 阶段提交

提交历史按设计、计划、领域契约、持久化、CLI、可靠性、AI、人工审核、评测和交付材料递进，便于复盘解题过程；仓库中不包含真实密钥、数据库文件或运行缓存。
