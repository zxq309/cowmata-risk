# 活动量综合决策模块 · v1.0.0

读取原始V2 JSON，计算活动量、动态基线和活动证据，供综合算法调用。源码、示例、说明与验证材料分别归类。

| 要做什么 | 打开哪里 |
|---|---|
| 查看完整算法和接入方法 | [说明/技术说明.md](说明/技术说明.md) |
| 查看实测结论 | [说明/实测报告.md](说明/实测报告.md) |
| 看全部牛的实证图 | [PNG图](说明/图表/活动量规律_全部牛实测证据.png)（大型 PDF 保留原交付目录） |
| 接入运行源码 | [cowmata_activity_aux/](cowmata_activity_aux/) |
| 运行接入示例或查看参数 | [示例/example.py](示例/example.py)、[参数示例](示例/config.example.json) |
| 查看逐包、逐牛结果 | [验证/结果/](验证/结果/) |
| 重跑实测与软件测试 | [验证/脚本/](验证/脚本/)、[验证/tests/](验证/tests/) |

在本目录运行：

```text
python -m pip install .
python 示例/example.py --help
python -B -m unittest discover -s 验证/tests -v
# 真实数据重跑所需外部路径见 ../../data/README.md
```

Python接口为 `ActivityModule`、`Context`、`as_fusion_features`。两档门槛在现有10头牛500包数据上分别出现8/10、5/10头目标窗新提示，属于活动辅助证据；完整评价口径见实测报告。

状态快照、临时环境和逐包完整 JSONL 保留原交付目录，详见 [导入说明](../../docs/MIGRATION.md)。
