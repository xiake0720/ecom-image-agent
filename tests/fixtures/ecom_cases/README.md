# ecom_cases 目录说明

本目录用于存放当前项目的最小 benchmark / regression case。

当前冻结 3 个基础 case：

- `tea_single_can`
- `tea_gift_box`
- `non_tea_control_bag`

目录约定：

- `inputs/` 放原始上传素材
- `expected/` 放人工检查摘要、截图或基线说明
- `case.json` 放 benchmark 脚本直接读取的机器可读配置
- `README.md` 继续保留给人工阅读

当前阶段先冻结目录结构和 case 配置，不要求一次补齐所有 golden 产物。
