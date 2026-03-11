# 变更记录

## v0.2.0
- 将 `analyze_product` 从泛化文本分析升级为基于上传商品图的 SKU 级视觉分析
- 新增 NVIDIA 多模态商品分析 provider，模型为 `qwen/qwen3-5-122b-a10b`
- 为商品分析新增独立 `vision mock | real` 模式与环境变量配置
- 升级 `product_analysis.json` 结构，加入包装结构、视觉识别、材质猜测和视觉约束字段
- 重写 `analyze_product` prompt，显式禁止用行业常识卖点替代图片观察
- 对齐当前仓库为第二阶段真实 provider 接线状态的文档口径
- 接入 `NVIDIATextProvider`，通过 NVIDIA NIM 对接 GLM-5
- 接入 `RunApiGeminiImageProvider`，通过 RunAPI 对接 Gemini Image Gen
- 为文本与图片 provider 增加 `mock | real` 模式切换
- 将 `analyze_product`、`plan_shots`、`generate_copy`、`build_prompts` 接到真实文本 provider
- 将 `render_images` 接到真实图片 provider
- 保持 `overlay_text` 继续走 Pillow 中文后贴字
- 保持 Streamlit 单体应用、任务目录结构、节点顺序与下载链路不变

## v0.1.0
- 初始化 Streamlit 单体应用
- 建立 LangGraph 工作流骨架
- 支持本地上传、任务目录生成、mock 结果预览、单图下载、ZIP 下载
- 建立 `provider / services / workflows / ui` 分层结构
- 建立 Pillow 中文文本渲染基础能力
- 当前仍为 Mock MVP，未接真实 Gemini / OCR / 抠图

