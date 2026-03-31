# API 文档

统一返回结构：
```json
{
  "code": 0,
  "message": "ok",
  "data": {},
  "requestId": "..."
}
```

## 1. 健康检查
- `GET /api/health`

## 2. 主图生成
- `POST /api/image/generate-main`
- `multipart/form-data`
- 必填文件：`white_bg`
- 可选文件：`detail_files[]`、`bg_files[]`
- 文本字段：`product_name`、`platform`、`style_type`、`shot_count` 等

## 3. 详情页生成
- `POST /api/detail/generate`
- JSON 请求，核心字段：
  - `title`
  - `platform`（`tmall` / `pinduoduo`）
  - `style`（示例：`premium` / `value`）
  - `selling_points[]`
- 返回：模块数组、预览数据、导出资产清单

## 4. 任务查询
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`

## 5. 模板查询
- `GET /api/templates/main-images`
- `GET /api/templates/detail-pages`
- `POST /api/templates/detail-pages/preview`

## 6. 资产访问
- `GET /api/assets/{file_name}`
