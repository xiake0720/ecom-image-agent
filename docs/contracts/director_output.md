# director_output contract

## 文件
- `director_output.json`
- Python 模型：
  - `src/domain/director_output.py`

## 顶层字段
- `product_summary`
- `category`
- `platform`
- `visual_style`
- `shots`

## `shots[]`
- `shot_id`
- `shot_role`
- `objective`
- `audience`
- `selling_points`
- `scene`
- `composition`
- `visual_focus`
- `copy_direction`
- `compliance_notes`

## 说明
- `director_v2` 固定输出 8 张图位规划
- `prompt_refine_v2` 只消费这份结构化导演结果
- 不再向旧 `style_director / plan_shots` contract 兼容
