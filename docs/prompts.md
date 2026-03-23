# Prompt 说明

<<<<<<< HEAD
## 原则
- prompt 只服务于结构化输出
- 节点职责单一
- v1 prompt 和 v2 prompt 并存

## v1 prompt
- `analyze_product.md`
- `style_director.md`
- `plan_shots.md`
- `generate_copy.md`
- `generate_layout.md`
- `shot_prompt_refiner.md`
- `build_image_prompts.md`

## v2 新增 prompt

### `director_v2.md`
- 节点：
  - `src/workflows/nodes/director_v2.py`
- 目标：
  - 输出 `DirectorOutput`
- 约束：
  - 面向天猫茶叶商品
  - 输出 8 张图规划
  - 只允许结构化 JSON

### `prompt_refine_v2.md`
- 节点：
  - `src/workflows/nodes/prompt_refine_v2.py`
- 目标：
  - 输出 `PromptPlanV2`
- 约束：
  - `title_copy` 建议 4 到 8 字
  - `subtitle_copy` 建议 8 到 15 字
  - `render_prompt` 必须能直接交给图片模型执行
  - `layout_hint` 必须可供图片模型和 overlay fallback 共用
  - 只允许结构化 JSON
=======
## 一、文档目的
本文件用于说明项目中各类 prompt 的作用、边界和当前实现状态。

当前仓库已经不再只是第一阶段 Mock MVP 当前态，而是处于第二阶段**真实文本 provider 接线阶段**。  
因此当前 prompt 文件的作用包括：
- 维持节点职责清晰
- 约束真实文本 provider 的结构化输出
- 保持中间 JSON 与 workflow 契约稳定

即使当前已有真实文本 provider 接线，prompt 体系仍然必须服务于结构化 JSON 输出，而不是自由文本解析。

---

## 二、当前 prompt 分类
项目中的 prompt 按以下类别组织：

### 1. 商品分析类
建议文件：
- `analyze_product.md`

作用：
- 根据上传的商品图输出 SKU 级视觉分析结果，重点描述包装形态、标签布局、主色调、材质感和必须保留的视觉识别点
- `analyze_product` 是当前唯一看图节点；后续节点不应再次承担图片理解

输出目标：
- `product_analysis.json`

### 2. 图组规划类
建议文件：
- `plan_shots.md`

作用：
- 根据商品分析结果，规划一套电商图的图型结构
- 为每张图定义用途、卖点方向、尺寸与展示重点
- 先建立整组统一风格锚点
- 在通用品类下增加类目边界、核心图型与扩展图型约束
- 控制发散边界，避免出现与类目无关的喧宾夺主元素

输出目标：
- `shot_plan.json`

### 3. 文案生成类
建议文件：
- `generate_copy.md`

作用：
- 根据 `shot_plan` 为每个 shot 生成标题、副标题、卖点条目等结构化中文文案
- 控制字数、密度、表达风格
- 不承担图组规划职责

输出目标：
- `copy_plan.json`

### 4. 布局生成类
建议文件：
- `generate_layout.md`

作用：
- 约束 `generate_layout` 只负责标题区、副标题区、卖点区的坐标、尺寸和安全边距
- 为后续 Pillow 后贴字提供结构化定位信息
- 当前仓库运行时仍由规则布局生成，本文件用于固定职责边界，不代表已接入真实布局模型

输出目标：
- `layout_plan.json`

### 5. 图片提示词构建类
建议文件：
- `build_image_prompts.md`

作用：
- 为图片模型生成单张图、可直接使用的统一风格提示词
- 强调商品主体保持、包装比例保持、品牌元素不乱改
- 明确预留文案区域
- 当前 `build_prompts` 不再传图，只基于 `task + product_analysis + current shot + current copy + current layout` 逐张生成

输出目标：
- `image_prompt_plan.json`

### 6. 质检审查类
建议文件：
- `qc_review.md`

作用：
- 用于后续 OCR 质检、布局校验、人工复查辅助说明
- 当前阶段仍可保留占位说明

输出目标：
- `qc_report.json` 的补充说明或审查规则

---

## 三、当前阶段要求
当前 prompt 体系必须满足以下要求：
- 允许服务于真实文本 provider
- 继续保持文件分类清晰
- 必须围绕结构化 JSON 输出设计
- 必须避免“单个大 prompt 包办全部流程”的做法
- 必须与现有 workflow 节点职责一一对应

---

## 四、当前实现对齐说明
当前仓库中，prompt 已经开始服务以下真实文本节点：
- `plan_shots`
- `generate_copy`
- `build_prompts`

其中：
- `analyze_product` 已切换到真实视觉分析 prompt，不再由纯文本模型承担图片理解
- `build_prompts` 当前为纯结构化推理模式，不向文本模型发送图片输入
- `plan_shots` 当前模板已增加类目族群识别、整组风格锚点、核心图型与扩展图型约束

但仍然需要注意：
- `generate_layout` 目前没有切换到真实模型
- 图片模型不负责正式中文落图
- 正式中文仍统一通过 Pillow 后贴字完成

---

## 五、接入真实文本 provider 时必须遵守的规则

### 1. 输出优先结构化
每个节点的 prompt 都应以结构化 JSON 输出为目标，不允许退化为“自由文本 + 正则猜测”。

### 2. 保持节点单一职责
- 商品分析只做分析
- 图组规划只做规划
- 文案生成只做文案
- 布局生成只做坐标与版式
- 提示词构建只做图片生成提示词
- `build_prompts` 不重新做看图分析

### 3. 不让图片模型承担正式中文落图
图片模型只负责构图、主体保持和风格控制，不负责正式中文文字渲染。

### 4. 保持可落盘、可复查
每一步输出都要可落盘、可回放、可检查，避免黑箱式链路。

---

## 六、结论
当前 prompt 体系已经从“仅为 mock 预留”演进到“同时服务真实文本 provider 接线”。  
但它的核心原则没有变：分类正确、结构清晰、JSON 优先、不破坏现有 workflow 契约。

当前需要特别记住的三点是：
- 看图分析只在 `analyze_product`
- 图组边界和整组风格锚点由 `plan_shots` 先建立
- `build_prompts` 只基于结构化结果逐张生成 prompt，不再重复传图

>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
