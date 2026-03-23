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
- 项目不再区分 v1/v2 workflow
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
- 历史环境变量中的旧 provider 别名（如 `dashscope`）会被忽略，不再参与运行时分流
- 历史环境变量中的旧模型覆盖值也不会再改写 v2 固定模型

## RunAPI 图片响应
- Gemini 图片接口当前可能返回 `inlineData.data` 或 `fileData.fileUri`
- 当返回 `fileData.fileUri` 时，provider 会在内部自动下载图片字节后再进入落盘流程
- 图片主请求和 `fileUri` 下载请求都会显式关闭环境代理

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
