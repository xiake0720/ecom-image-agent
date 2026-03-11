# 第一阶段里程碑：Mock MVP

## 里程碑名称
第一阶段 Mock MVP

## 当前版本号
`v0.1.0-mock-mvp`

## 完成日期
2026-03-11

## 项目目标
构建一个本地运行的 Streamlit 单体应用，用于茶叶品类电商主图生成流程验证。用户上传一张或多张商品图，填写商品参数后，本地运行 LangGraph 工作流骨架，输出 mock 结果图，并通过 Pillow 完成中文后贴字，最终支持结果预览、单图下载和 ZIP 下载。此阶段明确定位为 mock MVP，不是真实生图 MVP。

## 第一阶段范围
本阶段纳入范围的内容：
- 使用 `streamlit_app.py` 作为唯一 UI 入口的 Streamlit 单体应用
- 本地文件上传
- 在 `outputs/tasks/{task_id}/` 下创建本地任务目录
- 使用结构化 schema 约束工作流输入输出
- LangGraph 工作流骨架与节点边界
- mock 任务执行与 mock 图片输出
- Streamlit 结果预览
- 单图下载与 ZIP 下载
- 使用 Pillow 完成中文后贴字基础能力
- schema 与文本渲染单元测试

本阶段不在范围内的内容：
- 真实 Gemini 文本分析
- 真实 Gemini 生图
- OCR 质检运行时
- rembg 抠图兜底
- 多模型 fallback 与路由
- 数据库、鉴权、消息队列、云部署、前后端分离

## 已完成能力
- 已完成可本地运行的 Streamlit 单体应用初始化
- 已完成品牌名、产品名、平台、尺寸、张数、文案风格等参数表单
- 已验证文件上传能力
- 已验证表单提交后创建 task_id 与本地任务目录
- 已完成可端到端跑通的 LangGraph workflow mock 骨架
- 已完成结果预览图显示
- 已完成单图下载
- 已完成 ZIP 下载
- 已完成结构化 JSON 产物落盘
- 已完成 Pillow 标题、副标题、卖点条目后贴字基础能力
- 已通过 schema 单元测试
- 已通过 Pillow 文本渲染单元测试

## 当前系统架构概览
- UI 层：位于 `src/ui/`，由 `streamlit_app.py` 统一进入
- Workflow 层：位于 `src/workflows/`，负责 LangGraph 图与节点编排
- Domain 层：位于 `src/domain/`，负责 Pydantic 结构化 schema
- Provider 层：位于 `src/providers/`，保留 provider 接口与当前 mock 实现
- Service 层：位于 `src/services/`，负责本地存储、渲染、规划、质检以及 OCR/rembg 占位服务
- 存储方式：仅使用本地文件系统，不接数据库

## 当前目录结构概览
- `streamlit_app.py`：唯一 Streamlit 入口
- `src/core/`：配置、常量、路径工具
- `src/domain/`：任务与工作流 schema
- `src/providers/`：provider 接口与 mock 实现
- `src/services/`：本地存储、渲染、规划、质检、OCR/rembg 占位实现
- `src/workflows/`：状态定义、图构建、节点实现
- `src/ui/`：上传表单、结果预览、下载组件
- `outputs/tasks/`：任务输入、结构化产物、预览图与导出文件
- `tests/unit/`：schema 与文本渲染测试
- `docs/`：工作流与里程碑文档

## 当前可运行能力验证结果
第一阶段已验证通过的能力：
- 文件上传：通过
- 参数表单提交：通过
- workflow 跑通：通过
- 预览图显示：通过
- 单图下载：通过
- ZIP 下载：通过
- 单元测试：通过（`2 passed`）
- Streamlit 入口导入：通过

验证说明：
- 当前工作流运行基于 mock 数据与确定性的占位图输出
- 第一阶段未调用真实 Gemini、PaddleOCR 或 rembg 运行时

## 当前输出产物说明
每个任务目录 `outputs/tasks/{task_id}/` 当前会落盘以下内容：
- `inputs/`：上传的原始商品图
- `task.json`：任务元数据
- `product_analysis.json`
- `shot_plan.json`
- `copy_plan.json`
- `layout_plan.json`
- `image_prompt_plan.json`
- `qc_report.json`
- `generated/`：mock 生成的基础图片
- `final/`：Pillow 后贴字后的最终图片
- `previews/`：用于 UI 展示的预览图
- `exports/`：用于整包下载的 ZIP 文件

## 当前限制与未完成项
- 当前是 mock MVP，不是真实生图 MVP
- 商品分析仍为 mock / 规则生成
- 图片生成仍为 mock 占位画布
- OCR 质检尚未完成，仅保留接口占位
- 抠图兜底尚未完成，仅保留接口占位
- 多模型 fallback 尚未完成
- 中文排版效果依赖本地可用中文字体
- 当前仅对茶叶品类做了优先支持

第一阶段尚未完成的能力：
- 真实 Gemini 文本分析
- 真实 Gemini 生图
- OCR 质检
- 抠图兜底
- 多模型 fallback

## 已知问题
- 当前输出图片为占位图，不具备真实商品一致性
- 当前布局效果适合骨架验证，但尚未达到生产级优化程度
- OCR 相关检查目前仅具备占位意义，未形成真实校验闭环
- 当前工作区中保留了阶段验证时产生的本地 smoke 任务产物

## 下一阶段建议
以下仅为下一阶段建议，本里程碑不实现：
- 在保持现有 workflow 契约稳定的前提下接入真实 Gemini 结构化文本分析
- 在保持当前 Streamlit 单体形态不变的前提下接入真实 Gemini 生图
- 在运行环境准备完成后接入 OCR 质检能力
- 为复杂素材接入 rembg 抠图兜底
- 在主路径稳定后补充 provider fallback 策略
- 在真实能力接入前继续保持架构边界清晰，避免扩展到非 MVP 范围

## 验收结论
第一阶段已可作为冻结归档的 mock MVP 里程碑。当前代码已经满足本地 Streamlit 单体骨架、结构化工作流边界、文件上传、参数提交、workflow 跑通、结果预览、单图下载和 ZIP 下载等阶段目标，可以在确认后进入下一阶段的真实能力接入工作。

