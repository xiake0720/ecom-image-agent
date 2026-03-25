# Architecture

## 目标
当前仓库是单体 Streamlit 应用，围绕 v2 电商图主链做最小可运行实现，重点是：

- 本地可运行
- 链路清晰
- 结构化落盘
- 易于回放和排查

## 分层

### `src/ui/`
- 只负责页面、交互和结果展示。
- 当前页面负责：
  - 上传外包装白底图
  - 上传产品补充参考图
  - 上传背景风格参考图
  - 输入品牌名、商品名
  - 选择整体风格类型
  - 输入一句风格补充说明
  - 配置张数、比例、分辨率
  - 执行任务并展示增量结果
- UI 不再负责：
  - 逐张图标题输入
  - 副标题输入
  - 卖点输入
  - 自定义元素和避免元素大段控制

### `src/workflows/`
- 只负责主链状态和节点编排。
- `graph.py` 固定为单链路执行器。
- `director_v2 -> prompt_refine_v2 -> render_images` 负责把高层产品意图逐层收紧为最终生图请求。

### `src/domain/`
- 只保留当前主链需要的 contract：
  - `asset`
  - `task`
  - `director_output`
  - `prompt_plan_v2`
  - `generation_result`
  - `qc_report`
  - `image_prompt_plan`（仅供 render fallback 兼容）

### `src/providers/`
- 只保留当前主链实际可用的文本与图片 provider。
- 图片 provider 负责接收：
  - 最终 render prompt
  - 产品参考图
  - 背景风格参考图

### `src/services/`
- 只保留素材选择、Pillow 后贴字、本地存储与 ZIP 导出等通用能力。

## 当前执行模式
- 唯一 UI 入口：`streamlit_app.py`
- 唯一 workflow：v2 固定主链
- 唯一存储介质：本地文件系统

## 当前关键约束
- 产品定位是“整套电商产品图生成器”，不是“手工配置每张图文案的编辑器”
- overlay fallback 保留，但内聚到 `render_images`
- 参考图中的可见文字不能进入广告 copy 链路
- 产品参考图与背景风格参考图必须分流处理
- `hero` 图必须在导演层、prompt 精修层、render 层都强调主体约 `2/3`
- 不是每张图都必须带字
- QC 仅保留最小闭环，不再做旧链路复杂审查
