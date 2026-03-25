# Providers

## 当前有效 provider

### 文本
- 默认模型：`gpt-5-nano`
- 默认 provider：`runapi_openai`
- mock provider：`GeminiTextProvider`
- `real` 模式下固定使用 `gpt-5-nano`

### 图片
- 默认模型：`gemini-3.1-flash-image-preview`
- 默认 provider：`runapi_gemini31`
- mock provider：`GeminiImageProvider`
- `real` 模式下固定使用 `gemini-3.1-flash-image-preview`

## 路由规则
- 项目不再区分 v1/v2 workflow。
- 文本能力只用于：
  - `director_v2`
  - `prompt_refine_v2`
- 图片能力只用于：
  - `render_images`
- 当 provider mode 为 `real` 时，路由固定为：
  - text -> `runapi_openai`
  - image -> `runapi_gemini31`
- 当 provider mode 为 `real` 时，模型固定为：
  - text -> `gpt-5-nano`
  - image -> `gemini-3.1-flash-image-preview`

## RunAPI Gemini 图片请求行为
- `render_images` 会把 `PromptPlanV2` 下发给 `RunApiGemini31ImageProvider`。
- provider 会把以下字段拼入最终图片请求文本：
  - `render_prompt`
  - `copy_strategy`
  - `text_density`
  - `should_render_text`
  - `title_copy`
  - `subtitle_copy`
  - `selling_points_for_render`
  - `layout_hint`
  - `typography_hint`
  - `subject_occupancy_ratio`
- provider 会在请求中明确区分两类参考图：
  - 产品参考图
    - 只用于保持包装结构、材质、颜色与标签一致
  - 背景风格参考图
    - 只用于学习背景氛围、色调、光线、空间层次和材质语言
- provider 会显式加入禁令：
  - 广告文案只允许使用当前流程下发的标题、副标题、卖点
  - `should_render_text=false` 的图位不应主动生成广告大字
  - 严禁转写、复用、概括任何参考图可见文字

## 背景风格参考图边界
- 背景风格参考图继续保留，但角色更明确：
  - 可以学习背景氛围
  - 可以学习光线
  - 可以学习色调
  - 可以学习场景感
  - 可以学习材质语言
- 明确不能做的事：
  - 不能提取广告文案
  - 不能替换产品主体
  - 不能修改包装结构
  - 不能改变品牌识别

## RunAPI 图片响应
- Gemini 图片接口当前可能返回：
  - `inlineData.data`
  - `fileData.fileUri`
- 当返回 `fileData.fileUri` 时，provider 会在内部自动下载图片字节后再进入落盘流程。
- 图片主请求和 `fileUri` 下载请求都会显式关闭环境代理。

## overlay fallback
- overlay fallback 不作为独立旧节点存在。
- 触发后由 `render_images` 在节点内部走兼容生成 + Pillow 后贴字。
- `final_text_regions.json` 记录：
  - `overlay_applied`
  - `fallback_used`
  - `fallback_reason`
  - `copy_strategy`
  - `text_density`
  - `should_render_text`
  - `copy_source`
  - `selling_points_for_render`
  - `selling_points_boxes`

## 配置项
保留的关键环境变量：

- `ECOM_IMAGE_AGENT_RUNAPI_API_KEY`
- `ECOM_IMAGE_AGENT_RUNAPI_TEXT_API_KEY`
- `ECOM_IMAGE_AGENT_RUNAPI_TEXT_BASE_URL`
- `ECOM_IMAGE_AGENT_RUNAPI_TEXT_MODEL`
- `ECOM_IMAGE_AGENT_RUNAPI_IMAGE_BASE_URL`
- `ECOM_IMAGE_AGENT_RUNAPI_IMAGE_MODEL`

默认值：

- `ECOM_IMAGE_AGENT_RUNAPI_TEXT_MODEL=gpt-5-nano`
- `ECOM_IMAGE_AGENT_RUNAPI_IMAGE_MODEL=gemini-3.1-flash-image-preview`

## 已移除
- 视觉分析 provider 路由
- 多 provider 图片分流器
- `image_edit` 独立配置体系
- `workflow_version` 相关 provider 分支
