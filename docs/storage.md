# 存储方案说明

## 1. 当前存储方案
当前默认是本地文件存储：
- 任务索引：`storage/tasks/index.json`
- 任务目录：`outputs/tasks/{task_id}/`
- 详情页结构化结果：写入任务目录（如 `detail_page_modules.json`）

## 2. 本地存储与远端存储切换
- 当前代码主路径仍是本地文件存储。
- `backend/storage/` 中已预留存储抽象（如 `StorageBackend`、`StorageFactory`），用于未来扩展。
- 在未完成实现前，不在文档中宣称“已支持远端对象存储”。

## 3. 文件组织规则

### 3.1 索引层
- `storage/tasks/index.json` 存储任务摘要列表。
- 每次任务创建或状态更新，由 `TaskRepository` 回写索引。

### 3.2 任务层
`outputs/tasks/{task_id}/` 常见内容：
- `task.json`：任务运行时主清单
- `inputs/`：上传原图
- `generated/`：模型生成原图
- `final/`：后处理最终图
- `exports/`：ZIP 导出包
- `prompt_plan_v2.json`、`qc_report.json` 等中间产物

## 4. 任务文件路径规则
- 任务文件访问统一通过：`/api/tasks/{task_id}/files/{file_name}`。
- `file_name` 为任务目录内相对路径（如 `final/shot_01.png`）。
- 后端会做路径越界校验，禁止访问任务目录之外文件。

## 5. 图片 URL 获取策略
- 后端 runtime 返回相对 URL（`/api/tasks/.../files/...`）。
- 前端通过 `resolveApiUrl` 拼接为当前环境下可访问绝对地址。

## 6. 后续扩展方向
- 引入对象存储（OSS/S3）时，应保持 API 协议稳定，优先在服务层与存储适配层扩展。
- 若产物 URL 改为签名直链，必须同步更新：
  - `docs/api.md`
  - `docs/workflow.md`
  - `docs/frontend-workbench.md`
  - `README.md`
