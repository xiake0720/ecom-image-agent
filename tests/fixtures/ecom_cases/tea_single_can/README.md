# tea_single_can

## 用途

标准茶叶单罐基线 case，用于验证：

- 主链路可跑通
- 茶叶类目不会明显跑偏
- per-shot prompt 调试产物完整

## 固定输入

- 上传素材数量：`1`
- 推荐文件：
  - `inputs/product_main.png`

## 固定 task 参数

```json
{
  "brand_name": "Baseline Tea",
  "product_name": "高山乌龙单罐",
  "platform": "taobao",
  "output_size": "1440x1440",
  "shot_count": 4,
  "copy_tone": "专业自然"
}
```

## 最小验收

- aggregate JSON 齐全
- `artifacts/shots/*/prompt.json` 数量等于 `4`
- `generated/`、`final/`、`previews/`、`exports/` 存在
- 不出现明显离题茶类场景
