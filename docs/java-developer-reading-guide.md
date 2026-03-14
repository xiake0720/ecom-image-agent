# Java 开发者阅读指南

## 1. 从 Java 视角怎么理解这个项目

### 先用熟悉的分层概念对照
- `streamlit_app.py` + `src/ui/pages/*.py`
  - 类似 Java Web 项目里的入口类加页面控制层。
  - 不完全等价于 Spring MVC `Controller`，因为这里没有 HTTP Controller，而是 Streamlit 事件驱动页面。
- `src/workflows/graph.py`
  - 类似“编排层”或“pipeline 配置类”。
  - 你可以把它看成 Java 里的一个显式任务编排器，负责把多个 service 串起来。
- `src/workflows/nodes/*.py`
  - 类似一组按顺序执行的 application service / use case handler。
  - 每个节点做一件事，输入输出都通过统一状态对象传递。
- `src/domain/*.py`
  - 类似 Java 里的 `DTO + VO + command/result schema`。
  - 这些类既是运行时数据结构，也是落盘 JSON contract。
- `src/providers/*.py`
  - 类似 Java 里的 `Gateway / Client / Strategy`。
  - 负责调用外部模型服务，屏蔽 HTTP 细节和不同 provider 差异。
- `src/services/*.py`
  - 类似 Java 里的 `Domain Service / Infrastructure Service`。
  - 负责布局规则、文字渲染、落盘、QC、参考图筛选等。
- `src/core/config.py`
  - 类似 Java 里的 `application.yml + @ConfigurationProperties + route resolver`。
- `src/workflows/state.py`
  - 类似 Java 里的“全链路上下文对象”，可以理解成 pipeline context。

### workflow 节点相当于什么
- 每个 workflow 节点都像一个“有明确输入输出的 service handler”。
- 这些节点不是随意相互调用，而是由 `graph.py` 统一注册顺序。
- 对 Java 开发者来说，可以把它理解成：
  - `StateGraph` 类似一个显式声明的责任链 / pipeline
  - `WorkflowState` 类似整个流水线共享的上下文对象

### provider/router 相当于什么
- `src/providers/router.py`
  - 类似 Java 里的工厂 + 策略路由器。
  - 根据配置返回不同 provider 实现。
- `src/providers/image/routed_image.py`
  - 类似带分流逻辑的 facade。
  - 有参考图时走 `image_edit`，没有时走 `t2i`。

### state / contract / json schema 相当于什么
- `WorkflowState`
  - 类似整个 pipeline 的 `Context`。
- `src/domain/*.py`
  - 类似 Java 的 DTO/VO。
- `docs/contracts/*.json`
  - 类似对外或跨层 contract 示例与 schema 文档。
- 任务目录里的 `*.json`
  - 相当于把运行时中间结果序列化保存，便于回放和排查。

## 2. 本项目里的 Python 常见写法

### dataclass
- 典型文件：
  - `src/workflows/state.py`
  - `src/providers/image/routed_image.py`
- 用法理解：
  - 类似 Java 里只承载数据的简单类，但写法更轻量。
  - 你可以把 `@dataclass(frozen=True)` 理解为“不可变轻量 POJO”。

### typing
- 常见写法：
  - `list[str]`
  - `dict[str, object]`
  - `Asset | None`
- 对应 Java 理解：
  - `list[str]` 类似 `List<String>`
  - `Asset | None` 类似“可空 Asset”
  - `TypedDict` 类似字段可选的 map contract

### Optional / list / dict
- Python 3.11 常直接写：
  - `str | None`
  - `list[Asset]`
  - `dict[str, object]`
- 不再需要老写法 `Optional[str]`，但语义一样。

### async / await
- 当前项目主链路基本不是 async 编排。
- 某些 provider 内部会有异步任务语义，但 workflow 对外仍按同步节点组织。
- 作为阅读者，先把整个仓库按同步调用理解就够了。

### pathlib
- 典型文件：
  - `src/core/config.py`
  - `src/workflows/nodes/render_images.py`
- `Path("outputs/tasks")`
  - 类似 Java 里 `Paths.get(...)`，但更常用。
- 常见操作：
  - `path / "file.json"` 等价于路径拼接。

### Pydantic
- 典型文件：
  - `src/domain/*.py`
- 对 Java 开发者来说，可以理解成：
  - “带校验能力的 DTO”
  - 同时负责反序列化、序列化、字段默认值、字段约束
- 常见方法：
  - `model_validate(payload)` 类似把 dict 转成强类型对象
  - `model_dump(mode="json")` 类似序列化成 JSON-friendly dict
  - `model_copy(update={...})` 类似创建带部分字段覆盖的新对象

### context manager
- 常见写法：
  - `with log_context(...):`
- 类似 Java 里的 `try/finally` 包装上下文，但更简洁。
- 用来在一段执行期间附加日志上下文或管理资源。

### Streamlit 状态管理
- 关键对象：
  - `st.session_state`
- 你可以把它理解成当前浏览器会话级别的页面状态容器。
- 当前项目中它主要用来保存：
  - 当前任务结果
  - 页面错误信息
  - 是否触发重新加载 runtime

## 3. 主链路怎么读

### 先从入口开始
1. 看 [`streamlit_app.py`](/D:/python/ecom-image-agent/streamlit_app.py)
   - 确认应用如何启动。
2. 看 [`src/ui/pages/home.py`](/D:/python/ecom-image-agent/src/ui/pages/home.py)
   - 确认上传、表单、preview/final 按钮、task state 如何组织。
3. 看 [`src/workflows/graph.py`](/D:/python/ecom-image-agent/src/workflows/graph.py)
   - 确认 workflow 顺序和依赖注入。

### 再看状态如何流转
- 关键文件：
  - [`src/workflows/state.py`](/D:/python/ecom-image-agent/src/workflows/state.py)
- 重点关注：
  - `WorkflowState` 里有哪些字段
  - 哪些字段会被后续节点消费
  - 哪些字段是纯调试字段，例如：
    - `render_generation_mode`
    - `render_reference_asset_ids`
    - `render_selected_main_asset_id`
    - `render_reference_selection_reason`

### 再按节点顺序看
1. `analyze_product`
   - 把商品图变成 `product_analysis.json`
2. `style_director`
   - 生成整组风格架构 `style_architecture.json`
3. `plan_shots`
   - 输出固定五图 `shot_plan.json`
4. `generate_copy`
   - 输出文案 `copy_plan.json`
5. `generate_layout`
   - 输出布局和 `text_safe_zone`
6. `shot_prompt_refiner`
   - 输出结构化单张 spec `shot_prompt_specs.json`
7. `build_prompts`
   - 转换成兼容旧链路的 `image_prompt_plan.json`
8. `render_images`
   - 选择参考图、决定 `t2i / image_edit`、组装最终执行 prompt
9. `overlay_text`
   - Pillow 后贴字生成最终图
10. `run_qc`
   - 输出 `qc_report.json`
11. `finalize`
   - 打包导出、更新任务状态

### 文件如何落盘
- 任务目录位置：
  - `outputs/tasks/{task_id}/`
- 主链路关键 JSON：
  - `task.json`
  - `product_analysis.json`
  - `style_architecture.json`
  - `shot_plan.json`
  - `copy_plan.json`
  - `layout_plan.json`
  - `shot_prompt_specs.json`
  - `image_prompt_plan.json`
  - `qc_report.json`
- 图片目录：
  - `generated/` 或 `generated_preview/`
  - `final/` 或 `final_preview/`
  - `exports/`

### 结果如何展示到 UI
- `home.py` 会把 workflow 返回结果归一化成可放进 `st.session_state` 的 dict。
- `result_view.py` 负责展示：
  - 预览图 / 成品图
  - debug 信息
  - QC 结果
  - 下载按钮
  - 日志

## 4. 如何排查问题

### 先看哪几类信息
- 第一层：页面右侧 debug 区
  - 看 `render_mode`
  - 看 `render_variant`
  - 看 `render_generation_mode`
  - 看 `render_reference_asset_ids`
  - 看 `image_provider_impl`
  - 看 `image_model_id`
  - 看 `cache_hit_nodes`
- 第二层：任务目录里的中间 JSON
- 第三层：节点日志
- 第四层：对应节点单元测试

### 如何判断是 prompt 问题
- 先看：
  - `style_architecture.json`
  - `shot_prompt_specs.json`
  - `image_prompt_plan.json`
- 常见症状：
  - 风格不统一：先看 `style_architecture.json`
  - 某张图主体描述不对：看 `shot_prompt_specs.json`
  - 实际执行 prompt 和 spec 不一致：看 `render_images` 日志里的 `execution_prompt`

### 如何判断是 provider 路由问题
- 先看页面 debug：
  - `image_provider_impl`
  - `image_model_id`
  - `render_generation_mode`
- 再看：
  - `src/core/config.py`
  - `src/providers/router.py`
  - `src/providers/image/routed_image.py`
- 常见症状：
  - 明明上传了参考图却还走 `t2i`
  - `generation_mode` 和实际 provider 行为不一致

### 如何判断是参考图选择问题
- 先看日志：
  - `selected_main_asset_id`
  - `selected_detail_asset_id`
  - `selected_reference_asset_ids`
  - `selection_reason`
- 再看：
  - [`src/services/assets/reference_selector.py`](/D:/python/ecom-image-agent/src/services/assets/reference_selector.py)

### 如何判断是布局或后贴字问题
- 看：
  - `layout_plan.json`
  - `text_safe_zone`
  - `safe_zone_score_breakdown`
  - `rejected_zones`
- 再看：
  - `TextRenderer` 自适应颜色日志
  - QC 里的 `text_background_contrast`
  - QC 里的 `text_area_complexity`

### 如何判断是缓存误导
- 先看结果页：
  - `cache_enabled`
  - `ignore_cache`
  - `cache_hit_nodes`
- 再看日志：
  - `[cache] node=... status=hit/miss/ignored key=...`
- 调试 provider / prompt / 贴字时，优先让 `ignore_cache=true`。

### 如何判断是 UI 问题
- 如果任务目录里的图片和 JSON 都正常，但页面显示不对：
  - 看 `src/ui/pages/result_view.py`
  - 看 `src/ui/components/download_panel.py`
  - 看 `src/ui/pages/home.py` 的 `_normalize_task_state()`

### 如何判断是 QC 问题
- 看：
  - `qc_report.json`
  - `src/services/qc/task_qc.py`
  - `src/workflows/nodes/run_qc.py`
- 当前 QC 不是审美模型，而是轻量风险筛查：
  - `text_background_contrast`
  - `text_area_complexity`
  - `safe_zone_overlap_risk`
  - `product_consistency_risk`

## 5. 建议阅读顺序

### 第一遍：30 分钟建立全局图
1. [`docs/codebase-file-map.md`](/D:/python/ecom-image-agent/docs/codebase-file-map.md)
2. [`docs/architecture.md`](/D:/python/ecom-image-agent/docs/architecture.md)
3. [`docs/workflow.md`](/D:/python/ecom-image-agent/docs/workflow.md)
4. [`streamlit_app.py`](/D:/python/ecom-image-agent/streamlit_app.py)
5. [`src/ui/pages/home.py`](/D:/python/ecom-image-agent/src/ui/pages/home.py)
6. [`src/workflows/graph.py`](/D:/python/ecom-image-agent/src/workflows/graph.py)
7. [`src/workflows/state.py`](/D:/python/ecom-image-agent/src/workflows/state.py)

### 第二遍：按主链路读数据 contract
1. `task.py`
2. `asset.py`
3. `product_analysis.py`
4. `style_architecture.py`
5. `shot_plan.py`
6. `copy_plan.py`
7. `layout_plan.py`
8. `shot_prompt_specs.py`
9. `image_prompt_plan.py`
10. `generation_result.py`
11. `qc_report.py`

### 第三遍：按节点读实现
1. `analyze_product.py`
2. `style_director.py`
3. `plan_shots.py`
4. `generate_copy.py`
5. `generate_layout.py`
6. `shot_prompt_refiner.py`
7. `build_prompts.py`
8. `render_images.py`
9. `overlay_text.py`
10. `run_qc.py`
11. `finalize.py`

### 第四遍：按常见问题读细节
- provider / 模型路由：
  - `config.py`
  - `router.py`
  - `routed_image.py`
- 参考图策略：
  - `reference_selector.py`
- 文字渲染：
  - `text_renderer.py`
- 页面调试与缓存：
  - `home.py`
  - `result_view.py`
  - `cache_utils.py`

## 6. 给 Java 开发者的阅读建议

### 不要一开始陷在 Python 语法里
- 先抓三件事：
  - 状态对象是什么
  - 节点顺序是什么
  - 每个节点落盘什么文件

### 这个仓库不是“到处直接调模型”
- 所有真实模型调用都尽量收敛在 `src/providers/`。
- 如果你发现 UI 或 workflow 节点里出现大量 HTTP 细节，那通常说明代码开始失控了。

### 看不懂某段逻辑时，先找对应 JSON 产物
- Python 代码里中间变量多，容易一眼看晕。
- 但这个项目的优势是大部分关键步骤都会落盘。
- 先看落盘 JSON，再回看节点代码，通常比硬啃代码快。

### 调试时优先读日志和任务目录，不要先猜
- 当前项目已经专门补了 cache/render/overlay 调试摘要。
- 对 Java 开发者来说，可以把任务目录理解成“单次请求的完整离线快照”。
