# 温度辅助决策模块 · v0.6.0

接入综合算法使用本目录。运行源码在 `cowmata_temperature_aux`，完整算法与参数说明单独放在“说明”。

| 要做什么 | 打开哪里 |
|---|---|
| 查看算法、输入输出和注意事项 | [说明/技术说明.md](说明/技术说明.md) |
| 接入温度模块 | [cowmata_temperature_aux/](cowmata_temperature_aux/) |
| 运行原JSON或状态恢复示例 | [示例/example.py](示例/example.py) |
| 查看输出字段规范 | [output.schema.json](cowmata_temperature_aux/output.schema.json) |

在本目录安装：

```text
python -m pip install .
python 示例/example.py --help
```

Python接口为 `TemperatureModule`、`Context`、`as_fusion_features`。每头牛的每次设备绑定单独建实例，具体调用代码和参数见技术说明。

原交付引用的温度验证目录未随本次源码提供，详见 [导入说明](../../docs/MIGRATION.md)。
