# 架构说明

## 1. 当前仓库定位

`ecom-image-agent` 当前处于“真实 provider 接线 + 可观测性增强”阶段，目标不是生产化部署，而是：
- 本地可运行
- workflow 节点职责清晰
- 中间产物结构化落盘
- 便于回放、对比和排查问题

当前主场景是茶叶礼盒电商图生成，已经升级为“三层结构化视觉导演架构”：
1. `analyze_product`
   - 生成商品锁定分析 `product_analysis.json`
2. `style_director`
   - 生成整组风格架构 `style_architecture.json`
3. `shot_prompt_refiner`
   - 生成单张结构化 spec `shot_prompt_specs.json`
4. `render_images`
   - 基于结构化 spec + 商品锁定 + 参考图执行真实生成

## 2. 分层架构

### UI 层：`src/ui/`
- 职责：
  - 上传素材
  - 收集任务参数
  - 展示结果、日志、QC、调试信息
  - 管理 `st.session_state`
- 关键文件：
  - [`streamlit_app.py`](/D:/python/ecom-image-agent/streamlit_app.py)
  - [`src/ui/pages/home.py`](/D:/python/ecom-image-agent/src/ui/pages/home.py)
  - [`src/ui/pages/task_form.py`](/D:/python/ecom-image-agent/src/ui/pages/task_form.py)
  - [`src/ui/pages/result_view.py`](/D:/python/ecom-image-agent/src/ui/pages/result_view.py)
- 边界：
  - 不直接写模型 HTTP 调用
  - 不承载复杂 provider 路由逻辑

### Workflow 层：`src/workflows/`
- 职责：
  - 定义 `WorkflowState`
  - 定义 `WorkflowDependencies`
  - 注册 LangGraph 节点顺序
  - 包装统一日志、异常、缓存摘要
- 关键文件：
  - [`src/workflows/graph.py`](/D:/python/ecom-image-agent/src/workflows/graph.py)
  - [`src/workflows/state.py`](/D:/python/ecom-image-agent/src/workflows/state.py)
  - [`src/workflows/nodes/*.py`](/D:/python/ecom-image-agent/src/workflows/nodes)
- 边界：
  - 节点消费 service/provider，但不展开底层 HTTP 协议细节

### Domain 层：`src/domain/`
- 职责：
  - 定义任务、资产、分析结果、图组规划、布局、prompt、QC 等结构化 contract
- 关键点：
  - 所有核心落盘 JSON 都应该先有对应 domain model
  - provider 结构化输出也优先绑定到 domain model

### Provider 层：`src/providers/`
- 职责：
  - 封装文本、视觉、图片模型能力
  - 做 provider 路由与模型选择
  - 隔离 `t2i / image_edit` 分流
- 当前关键能力：
  - 文本：DashScope / Zhipu / NVIDIA / Ollama / mock
  - 视觉分析：DashScope / Zhipu / NVIDIA / mock
  - 图片生成：DashScope / RunAPI / mock
  - 图片编辑：DashScope image edit / 兼容 RunAPI

### Service 层：`src/services/`
- 职责：
  - 本地存储
  - 参考图筛选
  - shot 规划模板
  - 布局与安全区打分
  - Pillow 中文后贴字
  - QC 检查

## 3. 当前主链路

### Workflow 节点顺序
1. `ingest_assets`
2. `analyze_product`
3. `style_director`
4. `plan_shots`
5. `generate_copy`
6. `generate_layout`
7. `shot_prompt_refiner`
8. `build_prompts`
9. `render_images`
10. `overlay_text`
11. `run_qc`
12. `finalize`

### 为什么是这条链路
- `analyze_product`
  - 先锁定商品包装、文字、材质、结构比例，避免后续 prompt 发散。
- `style_director`
  - 先生成整组图统一视觉规则，而不是让每张图各自自由发挥。
- `plan_shots`
  - 茶叶类 Phase 1 固定五图，只让模型补充每张图的目标和方向。
- `shot_prompt_refiner`
  - 单独生成每张图的结构化 spec，避免旧版“一大段 prompt”难以调试。
- `build_prompts`
  - 对旧渲染链路做兼容桥接。
- `render_images`
  - 最终才根据参考图和 generation mode 组装执行 prompt 并调 provider。

## 4. 三层结构化视觉导演架构

### 第一层：商品锁定分析
- 文件：
  - [`src/domain/product_analysis.py`](/D:/python/ecom-image-agent/src/domain/product_analysis.py)
  - [`src/workflows/nodes/analyze_product.py`](/D:/python/ecom-image-agent/src/workflows/nodes/analyze_product.py)
- 作用：
  - 识别哪些包装元素必须保留，哪些区域可编辑。
- 关键字段：
  - `locked_elements`
  - `must_preserve_texts`
  - `editable_elements`
  - `package_type`
  - `primary_color`
  - `material`
  - `label_structure`

### 第二层：整组风格架构
- 文件：
  - [`src/domain/style_architecture.py`](/D:/python/ecom-image-agent/src/domain/style_architecture.py)
  - [`src/workflows/nodes/style_director.py`](/D:/python/ecom-image-agent/src/workflows/nodes/style_director.py)
- 作用：
  - 定义整套图统一风格世界观。
- 关键字段：
  - `style_theme`
  - `color_strategy`
  - `lighting_strategy`
  - `lens_strategy`
  - `prop_system`
  - `background_strategy`
  - `text_strategy`
  - `global_negative_rules`

### 第三层：单张结构化 spec
- 文件：
  - [`src/domain/shot_prompt_specs.py`](/D:/python/ecom-image-agent/src/domain/shot_prompt_specs.py)
  - [`src/workflows/nodes/shot_prompt_refiner.py`](/D:/python/ecom-image-agent/src/workflows/nodes/shot_prompt_refiner.py)
- 作用：
  - 为每张图定义结构化生成说明。
- 关键字段：
  - `subject_prompt`
  - `package_appearance_prompt`
  - `composition_prompt`
  - `background_prompt`
  - `lighting_prompt`
  - `style_prompt`
  - `quality_prompt`
  - `negative_prompt`
  - `layout_constraints`
  - `render_constraints`
  - `copy_intent`

## 5. 图片生成架构

### 参考图优先的图片生成分流
- 路由入口：
  - [`src/providers/router.py`](/D:/python/ecom-image-agent/src/providers/router.py)
  - [`src/providers/image/routed_image.py`](/D:/python/ecom-image-agent/src/providers/image/routed_image.py)
- 规则：
  - `reference_assets` 为空：走 `t2i`
  - `reference_assets` 非空：优先走 `image_edit`
- 当前调试字段：
  - `render_generation_mode`
  - `render_reference_asset_ids`
  - `render_image_provider_impl`
  - `render_image_model_id`

### prompt 不是直接原样透传
- `render_images` 会把以下信息程序化组装成最终执行 prompt：
  - `product_analysis`
  - `style_architecture`
  - 当前 shot 的 `ShotPromptSpec`
  - 当前 `text_safe_zone`
  - 当前 `generation_mode`
- 这样做的目的：
  - 让最终执行 prompt 可追溯
  - 避免 provider 只吃旧版单层 prompt

## 6. 布局与后贴字架构

### 布局
- `generate_layout` 当前不是 AI 检测模型，而是规则打分器。
- 核心目标：
  - 不压主体
  - 不压复杂纹理
  - 优先选择干净背景
  - 与 `build_prompts` 的 `text_safe_zone` 保持一致

### 后贴字
- 仍然坚持 Pillow 后贴字，不把中文文字直接交给图像模型生成。
- 当前补充了：
  - typography token
  - 背景自适应文字颜色
  - 阴影 / 描边 / 半透明底板策略
  - 两套 preset：`premium_minimal` / `commercial_balanced`

## 7. 可观测性设计

### 任务目录落盘
- 每次任务会落盘到：
  - `outputs/tasks/{task_id}/`
- 关键产物包括：
  - `product_analysis.json`
  - `style_architecture.json`
  - `shot_plan.json`
  - `copy_plan.json`
  - `layout_plan.json`
  - `shot_prompt_specs.json`
  - `image_prompt_plan.json`
  - `qc_report.json`

### 页面调试信息
- 结果页当前重点展示：
  - 是否命中缓存
  - 本次真实生成链路
  - preview / final
  - `t2i / image_edit`
  - 参考图 ID
  - 实际 provider / model

## 8. 当前非目标范围

当前仓库仍然明确不做：
- 前后端分离
- 数据库
- 登录鉴权
- 消息队列
- 云端部署
- 多租户
- 重型 CV 主体检测
- 复杂后台系统

## 9. 阅读建议

如果第一次进入仓库，建议按下面顺序：
1. [`docs/java-developer-reading-guide.md`](/D:/python/ecom-image-agent/docs/java-developer-reading-guide.md)
2. [`docs/codebase-file-map.md`](/D:/python/ecom-image-agent/docs/codebase-file-map.md)
3. [`docs/workflow.md`](/D:/python/ecom-image-agent/docs/workflow.md)
4. [`streamlit_app.py`](/D:/python/ecom-image-agent/streamlit_app.py)
5. [`src/ui/pages/home.py`](/D:/python/ecom-image-agent/src/ui/pages/home.py)
6. [`src/workflows/graph.py`](/D:/python/ecom-image-agent/src/workflows/graph.py)
