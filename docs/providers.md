# Provider 与模型路由说明

<<<<<<< HEAD
## 当前结论
- v2 文本默认模型：`gpt-5-nano`
- v2 图片默认模型：`gemini-3.1-flash-image-preview`
- 旧 provider 继续保留，新增 alias 不覆盖旧逻辑

## 入口
- `src/core/config.py`
- `src/providers/router.py`

## 文本 provider

### 支持的 alias
- `dashscope`
- `nvidia`
- `ollama`
- `zhipu`
- `runapi_openai`
- `mock`

### `runapi_openai`
- 文件：`src/providers/llm/runapi_openai_text.py`
- 基于：
  - `src/providers/llm/openai_compatible_text.py`
- 接口：
  - `POST {runapi_text_base_url}/chat/completions`
- 默认：
  - `runapi_text_base_url = https://runapi.co/v1`
  - `runapi_text_model = gpt-5-nano`
- API Key 优先级：
  1. `ECOM_IMAGE_AGENT_RUNAPI_TEXT_API_KEY`
  2. `ECOM_IMAGE_AGENT_RUNAPI_API_KEY`

## 图片 provider

### 支持的 alias
- `dashscope`
- `runapi`
- `runapi_gemini31`
- `mock`

### `runapi_gemini31`
- 文件：`src/providers/image/runapi_gemini31_image.py`
- 模型固定：
  - `gemini-3.1-flash-image-preview`
- 接口：
  - `POST /v1/models/{model}:generateContent`
- 支持：
  - `contents[].parts[].text`
  - `contents[].parts[].inlineData`
  - `generationConfig.responseModalities`
  - `generationConfig.imageConfig.aspectRatio`
  - `generationConfig.imageConfig.imageSize`
- 支持 1 到 2 张参考图
- 返回结果从 `inlineData` 解析 base64 图片并写盘

说明：
- `runapi_gemini31` 不再复用旧的全局图片模型默认值
- 原因是旧 DashScope/Wanx 默认模型会污染 Gemini 3.1 路由

## router 行为

### 文本
- `text_provider=runapi_openai`
  - 返回 `RunApiOpenAITextProvider`

### 图片
- `image_provider=runapi_gemini31`
  - 返回 `RunApiGemini31ImageProvider`
- `image_provider=dashscope`
  - 返回 `RoutedImageProvider`
  - 根据参考图和配置在 `t2i / image_edit` 间分流

## v2 渲染策略
- `render_images` 在 v2 下优先消费 `prompt_plan_v2`
- 直接图内出字优先
- 单张失败时才写出 overlay fallback 标记

## 关键配置项
- `workflow_version`
- `runapi_text_base_url`
- `runapi_text_model`
- `runapi_text_api_key`
- `runapi_api_key`
- `runapi_image_base_url`
- `direct_text_on_image`
- `enable_overlay_fallback`
- `default_image_aspect_ratio`
- `default_image_size`

## 调试字段
=======
## 1. 文档目的
本文档说明当前仓库中：
- 文本 provider 如何选择
- 视觉分析 provider 如何选择
- 图片 provider 如何选择
- `t2i / image_edit` 如何自动分流
- `render_images` 如何为 image_edit 组装最终执行 prompt
- 哪些调试字段可以帮助定位 provider 问题

## 2. 路由入口
当前 provider 总路由入口是：
- [`src/core/config.py`](/D:/python/ecom-image-agent/src/core/config.py)
- [`src/providers/router.py`](/D:/python/ecom-image-agent/src/providers/router.py)

理解方式：
- `Settings`
  - 负责解析配置和“应该走哪条路”
- `router.py`
  - 负责把解析结果真正实例化成 provider 对象

## 3. 三类能力的 provider

### 3.1 文本规划能力
- 作用节点：
  - `style_director`
  - `plan_shots`
  - `generate_copy`
  - `shot_prompt_refiner`
- 当前实现：
  - DashScope
  - Zhipu
  - NVIDIA
  - Ollama
  - mock

### 3.2 视觉分析能力
- 作用节点：
  - `analyze_product`
- 当前实现：
  - DashScope
  - Zhipu
  - NVIDIA
  - mock

### 3.3 图片生成能力
- 作用节点：
  - `render_images`
- 当前实现：
  - DashScope t2i
  - DashScope image_edit
  - RunAPI Gemini
  - mock

## 4. 图片 provider 自动分流

### 路由适配层
- 核心文件：
  - [`src/providers/image/routed_image.py`](/D:/python/ecom-image-agent/src/providers/image/routed_image.py)

### 分流规则
- 当 `reference_assets` 为空：
  - 使用 `t2i`
- 当 `reference_assets` 非空：
  - 优先使用 `image_edit`
- 如果 image_edit 未启用或当前路由未接通：
  - 回退到 `t2i`

### 当前关键配置
- `ECOM_IMAGE_AGENT_IMAGE_PROVIDER`
- `ECOM_IMAGE_AGENT_IMAGE_MODEL`
- `ECOM_IMAGE_AGENT_IMAGE_EDIT_PROVIDER`
- `ECOM_IMAGE_AGENT_IMAGE_EDIT_MODEL`
- `ECOM_IMAGE_AGENT_IMAGE_EDIT_ENABLED`
- `ECOM_IMAGE_AGENT_IMAGE_EDIT_PREFER_MULTI_IMAGE`
- `ECOM_IMAGE_AGENT_IMAGE_EDIT_MAX_REFERENCE_IMAGES`

## 5. render_images 与 provider 的关系
`render_images` 本身不直接处理 HTTP，而是做三件事：
1. 选择参考图
2. 组装最终执行 prompt
3. 调用统一的图片 provider

真正“走哪条生成链路”由 `RoutedImageProvider` 决定。

### image_edit prompt 来源顺序
当 provider 解析结果为 `image_edit` 时，`render_images` 当前优先使用三层 contract 组装执行 prompt：

1. `product_lock / product_analysis`
2. `style_architecture`
3. `shot_prompt_specs`

组装后的 prompt 会显式分成这些段落：
- `Product Identity Lock`
- `Global Style Architecture`
- `Current Shot Direction`
- `Layout And Text Safe Zone`
- `Render Constraints`
- `Negative Rules`

说明：
- 这一步是“结构化 contract 执行器”，不是简单把旧 prompt 拼接后透传。
- 如果缺少任一关键 contract，`render_images` 会回退到旧链路：
  - 优先 `edit_instruction`
  - 否则回退 `prompt`
- `t2i` 路径仍然兼容旧 prompt plan。

## 6. DashScope 图片链路

### DashScope 文生图
- 文件：
  - [`src/providers/image/dashscope_image.py`](/D:/python/ecom-image-agent/src/providers/image/dashscope_image.py)
- 特点：
  - 保留异步任务提交 + 轮询 + 下载模式
  - 当前兼容多种结果结构解析，包括：
    - `output.choices[].message.content[].image`
    - `output.results[].url`
    - `output.result_url`

### DashScope 参考图编辑
- 文件：
  - [`src/providers/image/dashscope_image_edit.py`](/D:/python/ecom-image-agent/src/providers/image/dashscope_image_edit.py)
- 特点：
  - 支持本地参考图路径
  - 会把参考图转成 API 可接受的输入
  - 保留异步任务模式

## 7. 当前调试字段

### 页面 debug 和 state 字段
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
- `render_generation_mode`
- `render_reference_asset_ids`
- `render_image_provider_impl`
- `render_image_model_id`
- `render_selected_main_asset_id`
- `render_selected_detail_asset_id`
- `render_reference_selection_reason`
<<<<<<< HEAD
=======

### 关键日志
- `[render] mode=... variant=... generation_mode=... refs=[...]`
- `selected_main_asset_id=...`
- `selected_detail_asset_id=...`
- `reference_asset_ids=[...]`
- `execution_source=image_edit_contract_mode|legacy_prompt_fallback|legacy_t2i_prompt`
- `has_product_lock=true|false`
- `has_style_architecture=true|false`
- `has_shot_prompt_spec=true|false`

## 8. 常见问题排查

### 上传了参考图但还是文生图
先查：
1. `render_reference_asset_ids` 是否为空
2. `render_generation_mode` 是否为 `image_edit`
3. `image_edit_enabled` 是否为 `true`
4. 当前 `image_edit_provider` 是否已接通
5. `execution_source` 是否已经进入 `image_edit_contract_mode`

### generation_mode 显示 image_edit，但结果没保留商品
先查：
1. `selected_main_asset_id` 是否选错
2. `product_analysis.json` 中 `product_lock` 信息是否完整
3. `shot_prompt_specs.json` 中 `product_lock / layout_constraints / negative_prompt` 是否完整
4. `render_images` 组装后的 `execution_prompt` 是否已经进入 `image_edit_contract_mode`
5. DashScope image_edit provider 是否拿到了本地参考图

### provider/model 切换后页面没变化
先查：
1. 是否重载 runtime
2. 是否命中缓存
3. debug 区中的 `image_provider_impl / image_model_id`

## 9. 修改 provider 路由时必须同步更新的文档
只要改了以下任一项，就必须同步更新本文档：
- provider 别名
- model 选择规则
- mock/real 切换逻辑
- `image_edit / t2i` 分流逻辑
- image_edit prompt 来源顺序
- fallback 行为
- provider 调试字段
## render_images contract cleanup
- `render_images` 在 `image_edit` 模式下，`Product Identity Lock` 段落现在会显式展开：
  - `must_preserve`
  - `must_preserve_texts`
  - `editable_regions`
  - `must_not_change`
- 这些字段会先做程序层清洗，避免把 tuple、dict items 或对象直接字符串化到 prompt 里。
- 因此调试日志中的 `keep_subject_rules / editable_regions` 现在应保持为干净字符串列表，不应再出现 `('must_preserve', [...])` 这类内容。
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
