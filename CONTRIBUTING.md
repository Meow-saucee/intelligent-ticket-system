# 贡献指南

感谢参与智能工单协同系统。普通代码、文档和测试目标可先通过 Issue 说明；安全漏洞不得公开提交 Issue，请遵循[安全政策](SECURITY.md)，只能通过 GitHub Security Advisories 的 “Report a vulnerability” 私下报告。所有改动都应保持小范围、可审查，并说明行为变化与验证方式。

## 开发环境

支持 Python 3.11 及以上版本。PowerShell 示例：

```powershell
python --version  # 确认版本为 Python 3.11 或更高
python -m venv .venv
\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

在提交前运行完整测试与编译检查：

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

## 提交约定

- 每个提交只解决一个小主题，提交信息清楚描述目的；不要把无关格式化、生成文件或本机运行产物混入提交。
- 新行为、修复和边界条件应配套测试；文档改动也请在提交说明中列出验证命令。
- 不得提交 API Key、Authorization 头、数据库、日志、未脱敏模型响应或本机绝对路径。
- 修改 Prompt、AI schema、模型客户端或评测逻辑时，必须同时提交固定样例集的测试或评测证据。
- CI 永远不使用真实模型密钥；真实在线结果只能按公开评测 schema 提交。

提交 Pull Request 前，请确认测试通过、工作区不含敏感材料，并在描述中说明已知限制。请勿在代码、Issue 或 Pull Request 中粘贴密钥、个人联系方式或未脱敏数据。
