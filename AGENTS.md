# AGENTS.md

## Scope
- 当前仓库阶段：第二阶段，真实 provider 接线与可观测性增强阶段。
- 项目目标：保证本地可运行、链路清晰、结构化落盘、便于回放与排查，不宣称生产可用。
- 不变边界：
  - Python `>=3.11,<3.12`
  - Streamlit 单体应用
  - LangGraph 工作流
  - 本地文件存储
  - Pydantic / schema 驱动的结构化 contract
  - Pillow 中文后贴字
  - 任务目录落盘到 `outputs/tasks/{task_id}/`
- 唯一 UI 入口：`streamlit_app.py`

## Working Rules
- 保持分层：
  - `src/ui/` 只负责页面、交互、展示、页面状态。
  - `src/workflows/` 只负责 state、节点编排、节点间数据流转。
  - `src/domain/` 只负责结构化数据 contract。
  - `src/providers/` 只负责模型能力与 provider 路由。
  - `src/services/` 只负责渲染、规划、落盘、质检等通用业务能力。
- 不得把 provider 调用散落到 UI 或 workflow 节点内部。
- 不得未经确认修改主 workflow 顺序。
- 任何结构化运行时数据，先在 `src/domain/` 定义，再由 workflow / service / provider 消费。
- 业务改动优先小步重构，避免无关推翻。

## Documentation Sync Rules
- `docs/` 是项目事实来源，`AGENTS.md` 只负责执行规则、索引和约束。
- `AGENTS.md` 必须保持简洁，不写成长篇设计说明；详细设计、示例、schema、行为说明统一写入 `docs/`。
- 只要本次代码改动影响以下任一项，必须同步更新相关文档；否则任务不算完成：
  - 工作流行为或节点输入输出
  - 配置项 / 环境变量
  - JSON contract / schema
  - 落盘产物或目录结构
  - UI 行为
  - provider 路由、模型切换、`image_edit` / `t2i` 分流
  - state 字段
  - 日志关键字段
  - 测试方式、验证命令、运行方式
  - 文件职责变化
- 任何新增 JSON 落盘产物、schema、state 字段、关键日志字段，都必须同步写入 `docs/contracts/` 或 `docs/workflow.md`。
- 中文后贴字相关改动，必须同步记录字体来源、fallback 状态、最小字号约束和测试产物位置。
- `analyze_product` / `product_analysis` 相关改动，必须同步记录 `must_preserve_texts` 提取规则、`text_anchor_status / text_anchor_source` 语义、provider 空返回时的 fallback 策略，以及新增的文字锚点日志字段。
- `generate_copy` 相关改动，必须同步记录贴图文案长度阈值、品牌漂移防护、shot-type copy 风格约束，以及 `original_length / normalized_length / copy_shortened / brand_anchor_valid` 等日志字段。
- 茶叶固定模板相关改动，必须同步记录 `package_template_family`、`asset_completeness_mode` 和最终命中的模板名。
- `shot_prompt_refiner` 相关改动，必须同步记录各 `shot_type` 的排他规则、`render_constraints` 分层，以及新增的 shot differentiation 日志字段。
- `render_images` image_edit contract assembly 相关改动，必须同步记录 prompt section 顺序、锁定规则分组方式，以及 `editable_regions_final` 等执行日志字段。
- 任何 UI 行为变化、任务状态变化、preview / final 行为变化，都必须同步更新 `docs/workflow.md` 或等价文档。
- 任何 provider 路由、模型切换、图像生成模式分流变化，都必须同步更新 `docs/providers.md` 或等价文档。
- 以后任何新增或修改的核心 Python 文件，都必须补齐：
  - 文件头中文模块说明
  - 核心类中文说明
  - 核心函数中文 docstring
  - 复杂逻辑中文注释
- 中文注释必须解释职责、输入输出、上下游关系或为什么这样做，不能只写低价值废话。
- 每次修改代码时，必须同步检查并更新：
  - `docs/codebase-file-map.md`
  - 受影响的 `docs/*`
  - 必要的 schema / contract 文档
- 优先检查和维护这些文档：
  - `docs/phase1-contract.md`
  - `docs/architecture.md`
  - `docs/workflow.md`
  - `docs/providers.md`
  - `docs/qc-policy.md`
  - `docs/contracts/*.json`
  - `docs/contracts/*.md`
- 如果推荐文档尚不存在，先在 `docs/` 下创建最接近职责的文件，再持续维护。

## Required Final Checklist
- 提交前必须执行文档同步检查：
  - 本次是否新增、删除、重命名或修改了配置项？
  - 本次是否改变了 workflow 节点输入输出、节点职责或节点顺序？
  - 本次是否改变了 JSON contract、schema 或落盘文件？
  - 本次是否改变了 API、UI、状态机或任务状态行为？
  - 本次是否改变了 preview / final 行为？
  - 本次是否改变了 provider 路由、模型选择或 `image_edit` / `t2i` 分流？
  - 本次是否改变了日志关键字段、QC 语义或调试方式？
  - 本次是否改变了测试命令、运行方式或验证步骤？
- 上述任一项为“是”，必须在同一任务里更新对应文档。
- 如果判断“无需更新文档”，最终总结必须明确说明理由。
- 最终总结必须单独列出：
  - 修改了哪些代码文件
  - 修改了哪些文档文件
  - 是否更新了 `docs/codebase-file-map.md`
  - 是否补了中文注释 / docstring
  - 未覆盖文件范围或后续建议

## Docs Source Of Truth
- 事实来源优先级：
  1. `docs/`：架构、workflow、provider、contract、QC、示例
  2. 代码：具体实现
  3. `AGENTS.md`：执行导航和约束
- 历史里程碑文档只做事实归档，不改写历史结论。
- 当前状态文档必须准确反映仓库现状。
- 未经文档和实现同时满足，不得宣称生产可用。
