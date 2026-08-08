# 测试结果

以下结果来自交付提交前的本地验证（Python 标准库 `unittest`，无真实 API 密钥）：

```text
python -m unittest discover -s tests -v
Ran 47 tests ...
OK

python -m compileall -q src tests
exit code: 0
```

测试覆盖领域校验、SQLite 重启持久化、CLI 跨进程、五条 seed、重复与并发、乐观锁、真实本机 HTTP 协议、严格 AI 输出、模型失败降级、人工确认/修改/拒绝、12 条评测样例加载和端到端验收。

没有可安全提交的 `AI_API_KEY`，因此本文不虚构在线模型分类准确率；配置真实兼容 API 后，可分别运行 README 中的 baseline 和 hardened 评测命令，报告会记录模型、Prompt 版本、样例文件哈希和各项指标。
