# COWMATA Risk · 综合预警决策

牛只繁殖与健康监测的决策层。当前主线是产犊实验，已接入温度和活动量两个辅助证据模块。

| 组件 | 当前版本 | 能力与入口 |
|---|---|---|
| 温度辅助证据 | 0.6.0 | [模块说明](modules/temperature/README.md)：个体温度参照、持续温降、证据评分与时效权重 |
| 活动量辅助证据 | 1.0.0 | [模块说明](modules/activity/README.md)：原始 V2 IMU 活动特征、动态基线、活动证据 |
| 产犊融合 | 规划中 | [接入约定](docs/INTEGRATION.md)，尚未实现融合概率、预计时间或统一报警 |
| 发情、妊娠、健康风险 | 规划中 | 后续在本仓按任务扩展，暂不建立空算法包 |

本仓为私有实验仓。辅助证据不是独立产犊诊断；原始模型与参数保持导入版本，不在仓库整理中重新调参。

## 安装与验证

在仓库根目录执行，建议使用独立虚拟环境：

```sh
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest discover -s modules/activity/验证/tests -v
python -m unittest discover -s tests -v
python examples/calving_evidence_demo.py
```

两个模块原声明支持 Python >=3.8；仓库 CI 使用 Python 3.10 和 3.12。演示采用合成数据，展示真实模块的证据接口，不产生融合报警。

## 目录

```text
modules/temperature/  温度包、参数、输出 schema、示例、技术说明
modules/activity/     活动包、输出 schema、示例、既有测试与历史实验材料
examples/             两模块接入演示
tests/                安装后跨模块接口与状态恢复检查
docs/                 集成约定、导入溯源、验证记录
data/                 本地数据放置说明，实际数据不进入 Git
```

温度参数 `model.json` 是运行依赖，随包发布。训练集、原始包、数据库、视频和状态快照保留本地；历史实验结果与本次软件检查分别记录，详见 [数据说明](data/README.md) 和 [导入说明](docs/MIGRATION.md)。

## 四仓关系

- [cowmata](https://github.com/zxq309/cowmata)：总体架构、路线图与版本组合。
- [cowmata-tailring](https://github.com/zxq309/cowmata-tailring)：行为与事件模型训练、推理、评估。
- [cowmata-risk](https://github.com/zxq309/cowmata-risk)：本仓，辅助证据与下游决策。
- [cattle-tail-ring-annotator](https://github.com/zxq309/cattle-tail-ring-annotator)：人工标注、模型候选复核及导出。

本仓通过模块依赖或版本化数据交换使用其他组件，不复制识别算法或标注界面代码。
