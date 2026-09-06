# 本地实验数据

本次源目录中的 `综合决策20260906/温度数据集` 保留原位，含 SQLite、CSV 和原始标注。
将所需实验数据放到本目录或从外部绝对路径读取；data 下实际数据被 Git 忽略。

活动量真实实验脚本需要完整原始 JSON、产犊标注及可选历史参照；当前交付目录未包含脚本默认所需的“正常数据”。不要把脚本默认路径当成已经存在的数据。

示例（模块安装后，在本仓根目录执行，替换占位路径）：

```sh
python modules/activity/验证/脚本/validate_real_data.py --data-root /path/to/raw --labels /path/to/calving.csv --reference-v1 /path/to/reference-v1 --reference-v2 /path/to/reference-v2 --out runs/activity-validation
```

真实数据验证需要人工确认牛—设备绑定、采集/接收时间及真值口径。源码演示只使用合成数据。
