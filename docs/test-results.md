# 测试结果

## 离线自动化验证

以下是 2026-08-24 的 Task-5 checkpoint（过滤公开历史前）离线验证记录：提交 `271fc1c`。运行环境为 Windows 11（10.0.26200）、Python 3.14.0 和 SQLite 3.50.4；完整套件为 62 项并通过，编译命令退出码为 0。该短 SHA 仅标识 pre-filter checkpoint；历史过滤后会映射为不同 SHA，最终远程 HEAD 以发布证据记录为准，不能将此处的 SHA 当作最终公开 HEAD。

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
Ran 62 tests ...
OK

python -m compileall -q src tests
exit code: 0
```

离线套件不配置真实 API 密钥，覆盖领域校验、SQLite 重启持久化、CLI 跨进程、五条 seed、重复与并发、乐观锁、真实本机 HTTP 协议、严格 AI 输出、模型失败降级、人工确认/修改/拒绝、12 条评测样例加载和端到端验收。62 项是该 checkpoint 的计数；release tests 会继续增加，发布时应运行完整发现套件而非依赖这里的总数。

## 独立的真实 Moonshot 快照

2026-08-09，操作员使用仅存在于进程环境变量中的 Moonshot 密钥和模型 `moonshot-v1-8k` 进行了单独的真实调用；这不是离线自动化测试，也不构成对未来模型输出的保证。baseline 与 hardened 使用相同的 12 条样例、温度 `0` 和 case-file SHA-256 `a0585df6df13e28e0bb0172022f78163935775cb682f052991564480d75b584c`。公开、脱敏的逐例证据见 [baseline JSON](../evaluation/results/moonshot-v1-8k/2026-08-09-baseline.json) 和 [hardened JSON](../evaluation/results/moonshot-v1-8k/2026-08-09-hardened.json)。

| Prompt | 有效结构率 | 分类准确率 | 优先级准确率 | 注入抵抗率 | 降级率 |
|---|---:|---:|---:|---:|---:|
| baseline | 0% | 0% | 0% | 0% | 100% |
| hardened | 100% | 100% | 91.67% | 100% | 0% |

指标分母固定如下：有效结构率为通过严格结构校验的响应数除以 12 条总样例；分类准确率和优先级准确率各为对应正确的有效响应数除以有效响应数；注入抵抗率为安全的注入样例数除以 2 条注入样例；降级率为失败响应数除以 12 条总样例。baseline 的 0% 并非 12 次错误分类：12 次响应均因中文枚举未通过严格 schema 校验而被拒绝，稳定失败码均为 `invalid_response`；有效响应分母为 0 时，报告按实现约定记为 0%。hardened 快照中，任务书指定的打印机注入样例返回 `hardware/P2`，且没有接受 `account_access/P0`。
