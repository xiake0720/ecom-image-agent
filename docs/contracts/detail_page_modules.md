# detail_page_modules.json 契约

落盘位置：`outputs/tasks/{task_id}/detail_page_modules.json`

核心字段：
- `platform`：平台标识
- `style`：风格标识
- `title` / `subtitle`：商品标题信息
- `template_meta`：模板名称与版本
- `modules[]`：前端可直接渲染的模块数组
  - `id`
  - `name`
  - `layout`
  - `copy`
  - `assets[]`
