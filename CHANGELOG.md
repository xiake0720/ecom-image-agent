# 变更记录

## v0.2.0
- 收紧 `build_prompts`：当前改为纯结构化推理模式，不再向文本模型发送图片输入，参考商品图只在 `render_images` 阶段发送给真实图片模型
- 强化 `build_image_prompts.md`，按单张图输出更强的主体保持、构图、留白、平台风格与 negative prompt 约束
- 重写 `plan_shots.md`，增加类目族群识别、核心图型 / 扩展图型边界、整组统一风格锚点与发散边界控制
- 修正 `generate_copy.md` 与 `generate_layout.md` 的职责表述，避免文案、布局与图组规划职责漂移
- 为 `plan_shots` 与 `build_prompts` 增加中文日志，明确模板来源、类目族群、整组风格锚点，以及 `build_prompts` 未发送图片输入
- 新增模型能力路由层，统一处理视觉分析、结构化规划和图片生成三类能力的 provider 选择
- 默认主链路模型切换为 `qwen/qwen3.5-122b-a10b`
- 保留 `GLM-5` 作为文本链路可配置开关，不再需要改节点代码
- 将 `analyze_product` 从泛化文本分析升级为基于上传商品图的 SKU 级视觉分析
- 新增 NVIDIA 多模态商品分析 provider，模型为 `qwen/qwen3.5-122b-a10b`
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

