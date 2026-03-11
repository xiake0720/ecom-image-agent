# ecom-image-agent

这是一个面向茶叶品类的本地 Streamlit 电商生图工具第一阶段项目。当前版本为可运行的 mock MVP：用户上传商品图，填写参数，系统通过 LangGraph 工作流骨架生成占位结果图，并使用 Pillow 完成中文后贴字，随后支持预览、单图下载和 ZIP 下载。

## 当前项目状态
- 当前里程碑：`v0.1.0-mock-mvp`
- 当前阶段：第一阶段，mock MVP 冻结版本
- 当前形态：仅保留本地 Streamlit 单体应用
- 当前状态：工作流骨架与 mock 端到端流程已验证通过，尚未接入真实 Gemini / OCR / rembg 能力

## 第一阶段已完成内容
- 已完成 Streamlit 单体应用脚手架，唯一 UI 入口为 [streamlit_app.py](D:/python/ecom-image-agent/streamlit_app.py)
- 已完成本地文件上传
- 已完成本地任务目录生成
- 已完成 LangGraph workflow 骨架
- 已完成 mock 任务执行
- 已完成结果预览
- 已完成单图下载
- 已完成 ZIP 下载
- 已完成 provider / services / workflows / ui 分层结构
- 已完成 Pillow 文本渲染基础能力
- 已完成 schema 与文本渲染单元测试

## 安装方式
```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
python -m pip install -e .[dev]
```

## 当前运行方式
```bash
python -m streamlit run streamlit_app.py
```

## 环境变量
如需覆盖本地默认配置，可将 `.env.example` 复制为 `.env` 后再修改。当前版本为 mock MVP，不会调用真实 Gemini、PaddleOCR、rembg、数据库或任何云端服务。

## 目录说明
- `streamlit_app.py`：Streamlit 应用入口
- `src/domain/`：工作流领域模型与结构化 schema
- `src/providers/`：provider 接口与当前 mock 实现
- `src/services/`：本地存储、渲染、质检与辅助服务
- `src/workflows/`：LangGraph 状态、图定义与节点实现
- `src/ui/`：上传表单、结果预览、下载组件
- `outputs/tasks/`：任务输入、过程产物、预览图与导出文件
- `tests/unit/`：schema 与文本渲染测试
- `docs/workflow.md`：当前工作流说明文档

## 当前限制
- 当前仅对茶叶品类做了优先支持
- 当前图片输出仍为确定性的 mock 占位图，不是真实生图结果
- OCR 质检与抠图兜底目前仅保留接口占位，尚未接入真实运行时
- 中文排版效果依赖 `assets/fonts/` 下可用的中文字体文件

## 第二阶段计划
以下仅为计划说明，当前里程碑不实现：

- 在保持现有工作流契约稳定的前提下接入真实 Gemini 结构化文本分析
- 在保持 Streamlit 单体形态不变的前提下接入真实 Gemini 生图
- 在运行环境准备完成后接入 OCR 质检
- 为困难素材接入 rembg 抠图兜底
- 在主路径稳定后再考虑多模型 fallback

