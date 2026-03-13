# non_tea_control_bag

## 用途

非茶叶对照基线 case，用于验证：

- 类目边界没有回退成“全都按茶叶处理”
- `plan_shots` 不生成茶叶专属图型
- `build_prompts` 仍能稳定输出 per-shot prompt

## 固定输入

- 上传素材数量：`2`
- 推荐文件：
  - `inputs/product_main.png`
  - `inputs/product_detail.png`

## 固定 task 参数

```json
{
  "brand_name": "Baseline Bag",
  "product_name": "通勤托特包",
  "platform": "tmall",
  "output_size": "1440x1440",
  "shot_count": 4,
  "copy_tone": "简洁高级"
}
```

## 最小验收

- aggregate JSON 齐全
- `artifacts/shots/*/prompt.json` 数量等于 `4`
- `generated/`、`final/`、`previews/`、`exports/` 存在
- 不出现 `tea_soup`、`dry_leaf_detail`、`brewed_leaf_detail` 等茶叶专属图型
- 不出现茶席、茶汤、干茶、茶园等明显茶类场景
