# ExperimentGuard：游戏版本 A/B 实验评估工具

ExperimentGuard 是一个面向游戏版本迭代的轻量实验分析项目。它把 **分流质量、主指标、护栏指标、功效分析、CUPED 降方差和提前偷看控制** 串成一条可复现流水线，并输出可以直接发给策划、运营和研发的静态 HTML 报告。

项目支持 Python 3.10+，只使用标准库。克隆后不需要安装数据科学依赖，即可运行测试和完整演示。

[在线查看可复现示例报告](https://yuezhimin03.github.io/experiment-guard/) · [查看 CI](https://github.com/yuezhimin03/experiment-guard/actions)

## 为什么做这个项目

只比较两组均值很容易给出错误结论。真实版本评估至少需要回答：

- 分流是否发生 Sample Ratio Mismatch（SRM）？
- 留存提升是否有统计证据，区间有多宽？
- 崩溃率、付费率等护栏是否可接受？
- 当前样本量是否达到预先设定的最小可检测效应（MDE）？
- 中途查看结果时，显著性阈值是否需要收紧？
- 能否使用实验前行为降低指标方差？

ExperimentGuard 按这个顺序做检查，并把“为什么推广 / 为什么继续观察”写入报告。

## 一键运行

```bash
python -m unittest discover -s tests -v
python -m experiment_guard.cli demo --users 20000 --output-dir demo_output
```

运行后得到：

```text
demo_output/
├── experiment_users.csv   # 可复现的用户级模拟数据
├── analysis.json          # 机器可读结果
└── report.html            # 面向业务的静态报告
```

分析已有数据：

```bash
python -m experiment_guard.cli analyze your_experiment.csv \
  --experiment-name new_player_path_v2 \
  --output-dir analysis_output
```

输入数据需包含 `user_id`、`variant`、`d7_retained`、`payer`、`revenue`、`playtime_minutes`、`pre_playtime_minutes`、`crashed` 与 `session_count`。加载器会检查缺列、重复用户、非法分组、二值字段和负数指标。

## 架构

```mermaid
flowchart LR
  A["用户级实验 CSV"] --> B["数据契约与去重"]
  B --> C["SRM 分流检查"]
  C --> D["主指标 / 诊断指标"]
  D --> E["CUPED 降方差"]
  E --> F["护栏与非劣判定"]
  F --> G["功效 + O'Brien-Fleming 边界"]
  G --> H["决策理由"]
  H --> I["JSON + 静态 HTML 报告"]
```

核心模块：

- `experiment_guard/stats.py`：两比例检验、均值差、SRM、CUPED、bootstrap、样本量与序贯边界。
- `experiment_guard/analysis.py`：数据质量门禁、指标口径、护栏和最终决策。
- `experiment_guard/simulator.py`：固定随机种子的用户级游戏实验模拟器。
- `experiment_guard/report.py`：无外部资源的响应式 HTML 报告。
- `tests/`：9 个单元与端到端测试，覆盖统计函数、数据校验和完整分析链路。

## 可复现实验结果

在本仓库默认种子 `20260726`、20,000 名模拟用户上，本机运行结果如下（硬件与 Python 版本不同会影响耗时）：

| 项目 | 结果 |
|---|---:|
| 数据生成 + 完整分析 | 0.81 秒 |
| A / B 样本 | 10,089 / 9,911 |
| SRM p-value | 0.2082（通过） |
| D7 留存 | 28.30% → 31.23% |
| 留存绝对差 | +2.93pp，95% CI `[+1.66pp, +4.20pp]` |
| CUPED 游戏时长方差降低 | 55.6% |
| 测试 | 9 / 9 通过 |

示例最终给出“继续实验”的保守建议：虽然留存显著提升，但当前样本下付费率 `-0.3pp` 非劣护栏的置信区间仍过宽。这个结果刻意展示了工具不会因为单一主指标变好就直接建议上线。

## 统计口径

- **SRM**：期望 50/50 分流下的 1 自由度卡方检验，门槛 `p >= 0.001`。
- **D7 留存**：双侧两比例 z 检验，95% CI 使用非合并标准误。
- **连续指标**：Welch 标准误的大样本正态近似。
- **CUPED**：使用实验前游戏时长作为协变量，统一估计 `theta`。
- **护栏**：崩溃用户率 `+0.5pp`、付费率 `-0.3pp` 的非劣区间判定。
- **提前偷看**：根据已获得的信息比例计算 O'Brien-Fleming 型双侧边界。
- **功效**：根据当前基线、`alpha=0.05`、`power=0.80` 和默认 `MDE=1.5pp` 计算计划样本量。

更完整的推导与边界见 [docs/methodology.md](docs/methodology.md)。

## 面试时可以展开的设计点

1. 为什么必须把 SRM 放在效果检验之前，以及曝光日志和去重如何制造 SRM。
2. 为什么护栏要看差值置信区间和业务非劣界，而不只是“p > 0.05”。
3. CUPED 为什么能降方差，以及协变量必须在实验前确定。
4. 为什么连续查看固定 `0.05` 阈值会抬高假阳性率。
5. 如何将当前用户级 CSV 替换为数据仓库 SQL 输出，并按渠道、设备、版本做预先设定的分层分析。

## 适用边界

这是可审计的工程样例，不是通用统计软件。当前实现面向两个实验组和大样本近似；多组实验、极稀疏转化、复杂收入长尾和长期效应需要进一步增加多重比较、精确检验或分层模型。模拟数据只用于验证代码路径，不能作为真实游戏业务结论。

## License

[MIT](LICENSE)
