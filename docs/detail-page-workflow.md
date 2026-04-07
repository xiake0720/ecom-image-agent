# 茶叶详情图任务流（detail_page_v2）

## 目标
- 详情图任务独立于主图任务；
- 支持引用主图结果作为参考，不回写主图状态；
- 当前正式输出为 `3:4` 单屏详情图；
- 一次详情任务默认生成 `8` 屏，可配置到 `8-12` 屏；
- 输出规划、文案、prompt、结果图、QC 与 ZIP。

## 流程
1. `POST /api/detail/jobs` 接收 multipart 表单与素材；
2. 落盘 `inputs/request_payload.json` 与 `inputs/asset_manifest.json`；
3. 生成 `plan/detail_plan.json`；
4. 生成 `plan/detail_copy_plan.json`；
5. 生成 `plan/detail_prompt_plan.json`；
6. 渲染 `generated/*.png`；
7. 产出 `qc/detail_qc_report.json`；
8. 打包 `exports/detail_bundle.zip`。

## 运行时
- 轮询接口：`GET /api/detail/jobs/{task_id}/runtime`；
- 返回：当前阶段、进度、plan/copy/prompt、结果图、QC、ZIP。
