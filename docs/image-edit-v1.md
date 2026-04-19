# 单图局部编辑 v1

## 目标

阶段 6 提供“一期最小可用”的单张结果图二次优化能力：

- 用户在历史任务结果图上拖拽矩形选区。
- 用户输入编辑指令，例如“修改局部文案”“优化某块视觉区域”“保留主体仅修改局部”。
- 后端创建 `image_edit` 类型任务，并通过 Celery worker 执行。
- 生成结果作为新的 `task_results` 派生版本写入数据库，并通过 `image_edits` 保留编辑历史。

## 数据模型

新增表：`image_edits`

核心字段：

- `source_result_id`：被编辑的原始 `task_results.id`。
- `edit_task_id`：本次编辑对应的 `tasks.id`，任务类型固定为 `image_edit`。
- `edited_result_id`：编辑完成后生成的新 `task_results.id`。
- `selection_type`：当前实现 `rectangle`，预留 `mask`。
- `selection`：归一化坐标，当前为 `{ x, y, width, height, unit: "ratio" }`。
- `instruction`：用户编辑指令。
- `mode`：执行模式。当前 provider 没有原生 inpainting 接口，因此写入 `full_image_constrained_regeneration`。
- `status`：`pending | queued | running | succeeded | failed | cancelled`。

生成的新 `task_results`：

- `result_type = "image_edit"`。
- `parent_result_id = source_result_id`。
- `version_no` 按源结果及其直接派生结果递增。
- `render_meta.mode` 明确记录执行模式。
- `render_meta.selection` 保留本次矩形选区。
- `render_meta.local_relative_path` 保持旧文件接口兼容。

## API

### `POST /api/v1/results/{result_id}/edits`

按当前登录用户校验 `result_id` 所属权，创建图片编辑任务。

请求体：

```json
{
  "selection_type": "rectangle",
  "selection": {
    "x": 0.1,
    "y": 0.1,
    "width": 0.5,
    "height": 0.4,
    "unit": "ratio"
  },
  "instruction": "保留主体，仅优化选中区域的文字和光影"
}
```

响应返回 `image_edits` 摘要，包含 `edit_task_id`、`mode`、`status`。

### `GET /api/v1/results/{result_id}/edits`

返回当前用户对该结果图的编辑历史。若编辑已完成，`edited_result` 内返回派生 `task_results` 摘要和可预览 `file_url`。

## 执行流

1. API 校验当前用户拥有源 `task_results`。
2. 后端创建 `tasks` 行，`task_type = image_edit`，状态为 `queued`。
3. 后端创建 `image_edits` 行，记录选区、指令、fallback mode。
4. Celery 启用时调用 `ecom.image_edit.run`；本地开发未启用 Celery 时使用同一执行服务的后台线程 fallback。
5. worker 读取源图本地兼容路径，复制到编辑任务目录 `inputs/source.*`。
6. 当前无原生局部重绘 provider，构造“全图约束再生成” prompt，并把源图作为 reference asset 传给现有图片 provider。
7. 生成图写入 `outputs/tasks/{edit_task_id}/final/edited_result.png`。
8. 后端写入新的 `task_results`，更新 `image_edits.edited_result_id`，记录任务事件。

## 前端

入口在历史任务页结果卡片：

- 图片结果显示 `局部编辑` 按钮。
- 展开后显示原图、矩形选区、编辑指令输入框、示例指令、编辑历史。
- 矩形选区使用 pointer events 和普通 DOM/CSS 实现，不引入重型绘图框架。
- 编辑历史展示状态、执行模式、编辑指令、派生版本预览。

## 兼容与限制

- 不改主图/详情图核心生成逻辑。
- 继续复用现有 provider router 和 `generate_images` 能力。
- 当前 COS 模式下，编辑 worker 仍依赖源图存在本地兼容路径；如果源图仅存在 COS，服务会返回明确错误。后续需要补 worker 侧 COS 下载能力。
- 当前只实现矩形选区；schema 和表字段已预留 `mask`，前端组件可扩展 brush/mask。
- 当前不做图层系统、不做 Photoshop 式复杂编辑。

## 验收点

- 登录用户可在结果图上框选区域并提交编辑指令。
- 创建后可在 `/api/v1/tasks?task_type=image_edit` 看到编辑任务。
- 编辑完成后可在源结果的编辑历史看到新版本。
- 用户 A 不能通过结果编辑 API 查看或创建用户 B 的编辑记录。
