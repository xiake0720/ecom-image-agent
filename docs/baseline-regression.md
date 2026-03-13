# 最小可回归基线

## 1. 文档目的

本文件用于冻结当前仓库的最小可回归基线，服务两类目标：

- 后续改动后快速确认 workflow 主链路没有被破坏
- 为后续补齐真实 fixture、录制产物和回归脚本提供统一目录与断言口径

本文件只定义基线，不改变任何业务逻辑、provider 行为、prompt 内容或 workflow 顺序。

---

## 2. 当前基线边界

本次冻结的基线仍严格遵守当前仓库边界：

- Python 3.11
- Streamlit 单体应用
- LangGraph 10 节点顺序不变
- 本地任务目录落盘
- Pillow 中文后贴字
- `mock / real` 模式继续保留
- aggregate JSON 文件继续保留

本文件不把“理想结果”写成“当前已实现能力”。

---

## 3. 基线分层

为了避免把模型波动误判为工程回归，当前最小回归基线分成两层：

### A. 结构回归基线

这一层是当前最小、最稳定、最应该优先自动化的基线，适用于 mock 和 real：

- workflow 能跑通
- 节点顺序不变
- 任务目录结构不变
- 中间 JSON 文件齐全
- per-shot 调试产物齐全
- `generated/`、`final/`、`previews/`、`exports/` 产物存在
- `build_prompts` 继续逐张产出 `prompt.json`

### B. 语义回归基线

这一层用于后续 fixture 完整后再逐步增强，目前只建议做“弱约束断言”，不要把 LLM 文案或 prompt 长文本逐字冻结：

- 茶叶 case 不应规划出明显离题场景
- 茶礼盒 case 不应丢失礼赠 / 包装展示维度
- 非茶叶对照 case 不应回退成茶叶图型逻辑
- `build_prompts` 仍然不向文本模型发送图片输入
- `analyze_product` 仍然是唯一看图分析节点

---

## 4. 当前最小可回归 case 集

当前最小 case 集只保留 3 组：

1. `tea_single_can`
2. `tea_gift_box`
3. `non_tea_control_bag`

选择原则：

- 至少一个标准茶叶单罐 case
- 至少一个更复杂的茶礼盒 case
- 至少一个非茶叶对照 case，用于防止类目边界回退成“全都按茶叶处理”

---

## 5. case 总表

| case_id | 目的 | 建议类目预期 | 上传素材数量 | 建议输出尺寸 | 建议张数 |
| --- | --- | --- | --- | --- | --- |
| `tea_single_can` | 验证标准茶叶单罐链路与茶叶图型边界 | `tea` | 1 | `1440x1440` | 4 |
| `tea_gift_box` | 验证茶礼盒 / 礼赠导向 / 包装展示链路 | `tea` 或 `gift_set`（弱约束） | 2 | `1440x1920` | 5 |
| `non_tea_control_bag` | 验证非茶叶类目不会回退成茶席 / 茶汤 / 干茶逻辑 | `bag` | 2 | `1440x1440` | 4 |

说明：

- “建议类目预期”是语义弱约束，不建议在当前阶段逐字精确断言 `subcategory`
- 当前阶段更适合断言“没有明显跨类目跑偏”

---

## 6. 共享固定输入

所有 case 都建议固定以下输入维度，避免回归测试时混入无关变量：

### 6.1 上传素材

- 文件名固定
- 主商品图始终保留 1 张清晰 packshot
- 如存在第 2 张素材，固定为侧面 / 细节 / 礼盒内构成图，不混入生活场景图
- 图片格式统一优先 `png` 或 `jpg`

### 6.2 task 参数

每个 case 至少固定：

- `brand_name`
- `product_name`
- `platform`
- `output_size`
- `shot_count`
- `copy_tone`

不建议在基线阶段引入更多可变 task 参数。

---

## 7. case 详细定义

### 7.1 `tea_single_can`

#### 固定输入

- 上传素材数量：`1`
- 素材建议：
  - `inputs/product_main.png`
  - 内容：单罐茶叶正视或 3/4 视角 packshot，背景干净，不带复杂道具

#### 固定 task 参数

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

#### 预期中间产物

至少应存在：

- `task.json`
- `product_analysis.json`
- `shot_plan.json`
- `copy_plan.json`
- `layout_plan.json`
- `image_prompt_plan.json`
- `qc_report.json`
- `artifacts/shots/shot-01/shot.json`
- `artifacts/shots/shot-01/copy.json`
- `artifacts/shots/shot-01/layout.json`
- `artifacts/shots/shot-01/prompt.json`

建议断言：

- `shot_plan.shots` 数量为 `4`
- `copy_plan.items` 数量为 `4`
- `layout_plan.items` 数量为 `4`
- `image_prompt_plan.prompts` 数量为 `4`
- 每个 prompt 都有非空 `negative_prompt`
- `build_prompts` 继续按 per-shot 落盘 `prompt.json`

#### 预期最终产物

- `generated/` 中有 `4` 张基础图
- `final/` 中有 `4` 张后贴字图
- `previews/` 中有 `4` 张预览图
- `exports/{task_id}_images.zip` 存在

#### 语义弱约束

- 不应出现明显与茶叶无关的图型
- 不应出现茶席之外夸张离题道具堆叠
- 不应把单罐 case 规划成礼盒主导

---

### 7.2 `tea_gift_box`

#### 固定输入

- 上传素材数量：`2`
- 素材建议：
  - `inputs/product_main.png`：茶礼盒主 packshot
  - `inputs/product_detail.png`：礼盒局部 / 内托 / 侧面结构细节

#### 固定 task 参数

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

#### 预期中间产物

至少应存在：

- `task.json`
- `product_analysis.json`
- `shot_plan.json`
- `copy_plan.json`
- `layout_plan.json`
- `image_prompt_plan.json`
- `qc_report.json`
- `artifacts/shots/shot-01/prompt.json` 到 `artifacts/shots/shot-05/prompt.json`

建议断言：

- 四类 aggregate JSON 数量都和 `shot_count=5` 对齐
- 每张 `prompt.json` 都有 `preserve_rules`
- 每张 `prompt.json` 都有 `text_space_hint`
- `layout_plan.items[*].canvas_height` 应为 `1920`

#### 预期最终产物

- `generated/` 中有 `5` 张基础图
- `final/` 中有 `5` 张后贴字图
- `previews/` 中有 `5` 张预览图
- `exports/{task_id}_images.zip` 存在

#### 语义弱约束

- 图组中至少应保留包装 / 礼赠 / 陈列相关表达
- 不应退化成纯单罐茶图逻辑
- 不应完全丢失礼盒主体识别

---

### 7.3 `non_tea_control_bag`

#### 固定输入

- 上传素材数量：`2`
- 素材建议：
  - `inputs/product_main.png`：包袋正视或 3/4 视角主图
  - `inputs/product_detail.png`：肩带 / 五金 / 侧面细节

#### 固定 task 参数

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

#### 预期中间产物

至少应存在：

- `task.json`
- `product_analysis.json`
- `shot_plan.json`
- `copy_plan.json`
- `layout_plan.json`
- `image_prompt_plan.json`
- `qc_report.json`
- 每张 shot 对应的 `artifacts/shots/{shot_id}/prompt.json`

建议断言：

- `shot_plan.shots` 数量为 `4`
- `image_prompt_plan.prompts` 数量为 `4`
- 每张 prompt 都有 `composition_notes`
- 每张 prompt 都有 `style_notes`

#### 预期最终产物

- `generated/` 中有 `4` 张基础图
- `final/` 中有 `4` 张后贴字图
- `previews/` 中有 `4` 张预览图
- `exports/{task_id}_images.zip` 存在

#### 语义弱约束

- 不应出现 `tea_soup`、`dry_leaf_detail`、`brewed_leaf_detail` 这类茶叶专属图型
- 不应出现茶席、茶汤、干茶、产地茶园等明显茶类场景
- 应更接近 `bag` 的主体展示、材质、五金、肩带或上身相关表达

---

## 8. 当前最小断言清单

建议把回归检查按“必过”和“观察项”分开。

### 8.1 必过项

对 3 个 case 都至少检查：

- workflow 成功执行到 `finalize`
- `task.json` 存在
- `product_analysis.json` 存在
- `shot_plan.json` 存在
- `copy_plan.json` 存在
- `layout_plan.json` 存在
- `image_prompt_plan.json` 存在
- `qc_report.json` 存在
- `generated/` 非空
- `final/` 非空
- `previews/` 非空
- `exports/*.zip` 存在
- per-shot `prompt.json` 数量等于 `shot_count`

### 8.2 观察项

- `analyze_product` 是否仍然是唯一看图节点
- `build_prompts` 是否仍然不向文本模型发送图片输入
- `plan_shots` 是否仍先建立类目边界与整组风格锚点
- 茶叶 case 是否出现明显离题道具
- 非茶叶 case 是否回退成茶类图型

---

## 9. fixture 目录建议

建议在仓库中固定如下结构：

```text
tests/fixtures/ecom_cases/
  README.md
  tea_single_can/
    README.md
    inputs/
    expected/
  tea_gift_box/
    README.md
    inputs/
    expected/
  non_tea_control_bag/
    README.md
    inputs/
    expected/
```

目录职责建议：

- `inputs/`：放原始上传素材
- `expected/`：放人工确认后的参考说明、摘要 JSON、截图或 golden 结果说明
- `README.md`：只写该 case 的固定输入和验收口径

当前阶段不建议一开始就冻结大批 golden 图片，先冻结目录和断言口径即可。

---

## 10. 当前结论

当前最小可回归基线应优先冻结：

- 3 个 case
- 固定输入素材数量
- 固定 task 参数
- 固定中间 / 最终产物存在性
- 固定 per-shot 调试产物

而不是在现阶段去逐字冻结所有 LLM 文案或 prompt 内容。
