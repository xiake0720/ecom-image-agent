# tea_gift_box

## 用途

茶礼盒基线 case，用于验证：

- 礼盒 / 礼赠表达不丢失
- 纵向尺寸链路稳定
- 多素材输入下中间产物完整

## 固定输入

- 上传素材数量：`2`
- 推荐文件：
  - `inputs/product_main.png`
  - `inputs/product_detail.png`

## 固定 task 参数

```json
{
  "brand_name": "Baseline Tea",
  "product_name": "节礼茶礼盒",
  "platform": "tmall",
  "output_size": "1440x1920",
  "shot_count": 5,
  "copy_tone": "礼赠高级"
}
```

## 最小验收

- aggregate JSON 齐全
- `artifacts/shots/*/prompt.json` 数量等于 `5`
- `layout_plan.items[*].canvas_height` 为 `1920`
- `generated/`、`final/`、`previews/`、`exports/` 存在
- 图组中保留礼盒 / 包装展示维度
