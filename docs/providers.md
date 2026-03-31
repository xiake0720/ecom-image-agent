# Provider 与路由说明

## 主图生成
主图仍复用 `src/providers/` 与 `src/workflows/` 的既有 provider 路由逻辑。
FastAPI 仅做接口化封装，不改变 provider 选择策略。

## 详情页生成
详情页当前为模板组装能力，不依赖外部模型 provider。
后续可在 `backend/services/detail_page_service.py` 增加 copy/provider 接口以支持自动文案增强。
