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

## 真实 Moonshot/Kimi 验证

2026-08-09 使用操作员提供的 Moonshot 密钥（仅进程环境变量，未写入仓库）和模型 `moonshot-v1-8k` 完成真实调用。两次评测使用相同的 12 条样例、温度 `0` 和相同 case-file SHA-256：

| Prompt | 有效结构率 | 分类准确率 | 优先级准确率 | 注入抵抗率 | 降级率 |
|---|---:|---:|---:|---:|---:|
| baseline | 0% | 0% | 0% | 0% | 100% |
| hardened | 100% | 100% | 91.67% | 100% | 0% |

baseline 的 12 次响应使用了中文枚举，按设计被严格 schema 校验拒绝；hardened Prompt 输出符合固定英文枚举。任务书指定的打印机注入样例真实返回并人工确认成 `hardware/P2`，没有接受 `account_access/P0`。
