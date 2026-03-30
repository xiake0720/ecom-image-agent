# Node IO Map

| Node | 输入 | 输出 | 落盘 |
| --- | --- | --- | --- |
| `ingest_assets` | `task`, `assets` | `uploaded_files` | 无 |
| `director_v2` | `task`, `assets` | `director_output` | `director_output.json` |
| `prompt_refine_v2` | `task`, `director_output` | `prompt_plan_v2` | `prompt_plan_v2.json` |
| `render_images` | `task`, `assets`, `prompt_plan_v2` | `generation_result_v2`, `text_render_reports` | `generated/*`, `final/*`, `final_text_regions.json` |
| `run_qc` | `task`, `prompt_plan_v2`, `generation_result_v2`, `text_render_reports` | `qc_report_v2` | `qc_report.json` |
| `finalize` | `task`, `qc_report_v2`, `generation_result_v2` | `task`, `export_zip_path`, `full_task_bundle_zip_path` | `exports/*` |
