# AGENTS.md

## 当前仓库状态
本仓库当前处于**第二阶段：真实 provider 接线阶段**。  
第一阶段 **Mock MVP** 已经完成并归档，归档结论见：
- `docs/milestones/phase-1-mock-mvp.md`

当前仓库已经在第一阶段骨架基础上完成以下接线：
- 文本侧：`NVIDIATextProvider` + NVIDIA GLM-5
- 图片侧：`RunApiGeminiImageProvider` + RunAPI Gemini Image Gen
- 同时继续保留 `mock / real` 模式切换

但当前仓库**仍然不是生产可用系统**，仍以本地可运行、结构化落盘、链路清晰、便于检查与回放为优先目标。

---

## 不变的项目边界
无论第一阶段还是当前第二阶段，本项目都必须继续保持以下边界：
- Python 3.11
- Streamlit 单体应用
- LangGraph 工作流
- 本地文件存储
- Pydantic 结构化 schema
- Pillow 中文后贴字
- 本地预览与下载
- 任务目录落盘与中间 JSON 回放能力

唯一 UI 入口保持为：
- `streamlit_app.py`

---

## 历史阶段边界说明
第一阶段 **Mock MVP** 的历史边界仍然成立，但它属于**历史归档约束**，不再等同于“当前仓库现状”。

第一阶段重点验证的是：
- 上传商品图
- 填写品牌名、产品名、平台、尺寸、张数、文案风格等参数
- 创建本地任务目录
- 跑通 LangGraph 工作流骨架
- 生成占位结果图
- 使用 Pillow 完成中文后贴字
- 预览结果
- 单图下载与 ZIP 下载

第一阶段归档事实不允许被篡改，但当前仓库已经在该骨架上进入第二阶段真实 provider 接线。

---

## 当前阶段允许的实现范围
当前仓库允许维护和迭代以下内容：
- 第一阶段的本地骨架能力
- NVIDIA GLM-5 文本 provider 接线
- RunAPI Gemini Image Gen 图片 provider 接线
- `mock / real` 模式切换
- 结构化 JSON 输出校验与落盘
- 基于 Pillow 的中文后贴字链路
- 本地预览、单图下载、ZIP 下载

---

## 当前阶段明确禁止的内容
当前阶段仍然明确不做：
- FastAPI 或前后端分离
- 数据库
- 登录鉴权
- 消息队列
- 云部署
- 多租户
- 真实 OCR 运行时
- 真实 rembg 抠图
- 多模型路由与 fallback
- 复杂后台管理系统

---

## 技术栈约束
- Python 版本固定为 `>=3.11,<3.12`
- UI 仅允许使用 Streamlit
- 工作流编排使用 LangGraph
- 数据结构与节点输入输出统一使用 Pydantic
- 中文文案渲染统一使用 Pillow
- 所有任务结果统一落盘到本地目录
- 当前阶段优先保证本地可运行与可检查，不做过度抽象

---

## 架构分层规则
### UI 层
位于 `src/ui/`，负责：
- 上传组件
- 参数表单
- 结果预览
- 下载按钮
- 页面状态管理

禁止在 UI 层直接编写复杂业务逻辑或直接发起模型 HTTP 请求。

### Workflow 层
位于 `src/workflows/`，负责：
- LangGraph 状态定义
- 图结构定义
- 节点编排
- 节点间数据传递

禁止在 workflow 节点中散落 provider 细节实现。

### Domain 层
位于 `src/domain/`，负责：
- 任务对象
- 资产对象
- 商品分析结果
- 图组规划结果
- 文案结构
- 布局结构
- 生成结果
- 质检结果

所有结构化数据必须优先通过 domain schema 表达。

### Provider 层
位于 `src/providers/`，负责：
- 文本模型 provider 接口
- 图片模型 provider 接口
- mock provider
- 当前真实 provider

所有真实模型调用都必须收敛在 provider 层，不允许写到 UI 或 workflow 节点内部。

### Service 层
位于 `src/services/`，负责：
- 本地存储
- 文本渲染
- 规划逻辑
- 质检逻辑
- OCR 占位接口
- 抠图占位接口

---

## 当前工作流节点
当前工作流节点顺序固定为：
1. `ingest_assets`
2. `analyze_product`
3. `plan_shots`
4. `generate_copy`
5. `generate_layout`
6. `build_prompts`
7. `render_images`
8. `overlay_text`
9. `run_qc`
10. `finalize`

允许节点内部存在 `mock / real` 分支，但不允许随意修改节点顺序、节点契约和落盘产物命名。

---

## 输出产物要求
每个任务必须落盘到：
`outputs/tasks/{task_id}/`

每个任务目录至少应包含：
- `inputs/`
- `task.json`
- `product_analysis.json`
- `shot_plan.json`
- `copy_plan.json`
- `layout_plan.json`
- `image_prompt_plan.json`
- `qc_report.json`
- `generated/`
- `final/`
- `previews/`
- `exports/`

---

## 中文文案渲染规则
最终图片中的中文文案，不依赖图片模型直接生成，而是统一走 Python 后贴字流程。

要求：
- 标题、副标题、卖点条目分层渲染
- 支持自动换行
- 支持缩字兜底
- 保持安全边距
- 避免裁字、溢出、遮挡主要商品主体

---

## 质量规则
当前阶段至少保证以下检查项：
- 输出尺寸正确
- 任务目录完整
- 结构化 JSON 可读
- 预览图可显示
- 单图下载可用
- ZIP 下载可用
- 文本渲染不报错

---

## 当前开发优先级
1. 保持 Streamlit 单体应用稳定可运行
2. 保持 workflow 骨架与 JSON 契约稳定
3. 保持本地存储与导出链路稳定
4. 保持 Pillow 中文后贴字能力可用
5. 保持真实 provider 接线清晰且可回退
6. 文档与测试同步完善

---

## 禁止事项
当前阶段禁止：
- 未经确认直接改成前后端分离
- 引入数据库或复杂基础设施
- 在 UI 中硬编码模型调用
- 在 workflow 节点中散落 provider 逻辑
- 虚构已经实现的真实能力
- 将“真实 provider 已接线”描述成“生产可用系统”

---

## 文档与提交要求
- 所有核心文档优先使用中文
- 保持 README、架构文档、工作流文档、变更记录同步更新
- 第一阶段里程碑文档作为历史归档保留，不改写归档事实
- 当前状态文档必须准确反映仓库现状
- 所有 TODO 必须可执行、可验证，避免空泛描述

