# 茶叶详情图任务流（detail_page_v2）

## 目标
- 详情图任务独立于主图任务
- 支持引用主图结果作为 `main_result`
- 当前正式输出固定为 `3:4` 单屏详情图
- 当前页数范围保持 `8-12`
- 输出规划、文案、prompt、结果图、review、QC 与 ZIP

## 输入
入口为 `POST /api/detail/jobs` 或 `POST /api/detail/jobs/plan`。

素材角色：
- `packaging_files`
- `dry_leaf_files`
- `tea_soup_files`
- `leaf_bottom_files`
- `scene_ref_files`
- `bg_ref_files`

关键文本字段：
- `brand_name`
- `product_name`
- `tea_type`
- `style_preset`
- `price_band`
- `target_slice_count`
- `selling_points_json`
- `specs_json`
- `brew_suggestion`
- `extra_requirements`
- `prefer_main_result_first`

## 执行链路
1. 接收 multipart 表单与素材
2. 落盘 `inputs/request_payload.json`
3. 落盘 `inputs/asset_manifest.json`
4. 生成 `inputs/preflight_report.json`
5. 生成 `plan/director_brief.json`
6. 生成 `plan/detail_plan.json`
7. 生成 `plan/detail_copy_plan.json`
8. 生成 `plan/detail_prompt_plan.json`
9. 渲染 `generated/*.png`
10. 写出 `generated/detail_render_report.json`
11. 写出 `review/visual_review.json`
12. 写出 `review/retry_decisions.json`
13. 写出 `qc/detail_qc_report.json`
14. 打包 `exports/detail_bundle.zip`

## V2 规划规则
- 模板固定为 `tea_tmall_premium_v2`
- 每页固定一个 `page_role`
- 每页固定一个 `primary_headline_screen_id`
- 每页固定 `single_screen_vertical_poster`
- 每页只讲一个主题
- 不允许左右分栏、双屏、拼贴

默认页职责会按素材可用性动态选择：
- `hero_opening`
- `dry_leaf_evidence`
- `tea_soup_evidence`
- `parameter_and_closing`
- `leaf_bottom_process_evidence`
- `brand_trust`
- `gift_openbox_portable`
- `scene_value_story`
- `brewing_method_info`
- `packaging_structure_value`
- `package_closeup_evidence`
- `brand_closing`

素材约束：
- 缺失 `dry_leaf` 时，不生成 `dry_leaf_evidence`
- 缺失 `leaf_bottom` 时，不生成 `leaf_bottom_process_evidence`
- 缺失 `tea_soup / scene_ref / bg_ref` 时，允许 AI 在对应页面内补足辅助素材
- `packaging / main_result` 是主锚点，必须至少存在其一

## Prompt 与渲染规则
- prompt 按页职责与素材绑定直接生成
- 不再递归拼接 `Prompt 草案=`
- `negative_prompt` 统一去重
- `title_copy / subtitle_copy / selling_points_for_render` 会随 prompt 一起下发
- 图内可见文字仅使用 `title_copy / subtitle_copy / selling_points_for_render`
- `body_copy / notes / 规则说明` 只用于规划与预览，不再写进 render prompt
- 首屏和包装主视觉页会显式补强接地感、接触阴影、环境遮蔽与统一光向
- 渲染阶段支持页级重试：
  - 原 prompt 重试
  - 降低文本密度
  - 参考重绑或强化包装保护

## QC 补充规则
- 拦截规则句、提示词或系统说明混入用户可见 copy
- 拦截参数卡中的英文 key 与 `snake_case`
- 检查首屏 prompt 是否具备接地感关键词
- 仍保留页数、参考绑定、锚点素材、比例等基础检查

## 运行时
轮询接口：
- `GET /api/detail/jobs/{task_id}/runtime`

返回内容包括：
- 当前阶段与进度
- `plan / copy_blocks / prompt_plan`
- `preflight_report / director_brief`
- `visual_review / retry_decisions`
- `qc_summary`
- `images`
- `export_zip_url`

## 任务状态
- `created`
- `running`
- `completed`
- `review_required`
- `failed`

状态解释：
- `completed`：全部页面成功且 QC 通过
- `review_required`：存在失败页、警告页或部分成功
- `failed`：0 页成功
