ecom-image-agent/
├─ AGENTS.md
├─ README.md
├─ pyproject.toml
├─ .env.example
├─ .gitignore
├─ streamlit_app.py
├─ Makefile
│
├─ src/
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ logging.py
│  │  ├─ constants.py
│  │  └─ paths.py
│  │
│  ├─ domain/
│  │  ├─ task.py
│  │  ├─ asset.py
│  │  ├─ product_analysis.py
│  │  ├─ shot_plan.py
│  │  ├─ copy_plan.py
│  │  ├─ layout_plan.py
│  │  ├─ image_prompt_plan.py
│  │  ├─ generation_result.py
│  │  └─ qc_report.py
│  │
│  ├─ providers/
│  │  ├─ llm/
│  │  │  ├─ base.py
│  │  │  ├─ gemini_text.py
│  │  │  └─ deepseek_text.py
│  │  ├─ image/
│  │  │  ├─ base.py
│  │  │  ├─ gemini_image.py
│  │  │  └─ wanx_image.py
│  │  └─ tracing/
│  │     └─ langsmith.py
│  │
│  ├─ services/
│  │  ├─ storage/
│  │  │  ├─ local_storage.py
│  │  │  └─ zip_export.py
│  │  ├─ analysis/
│  │  │  └─ product_analyzer.py
│  │  ├─ planning/
│  │  │  ├─ shot_planner.py
│  │  │  ├─ copy_generator.py
│  │  │  └─ layout_generator.py
│  │  ├─ rendering/
│  │  │  ├─ text_renderer.py
│  │  │  ├─ font_utils.py
│  │  │  └─ image_postprocess.py
│  │  ├─ ocr/
│  │  │  └─ paddle_ocr_service.py
│  │  ├─ bg_remove/
│  │  │  └─ rembg_service.py
│  │  └─ qc/
│  │     ├─ image_qc.py
│  │     ├─ ocr_qc.py
│  │     └─ copy_rules.py
│  │
│  ├─ prompts/
│  │  ├─ analyze_product.md
│  │  ├─ plan_shots.md
│  │  ├─ generate_copy.md
│  │  ├─ generate_layout.md
│  │  ├─ build_image_prompts.md
│  │  └─ qc_review.md
│  │
│  ├─ workflows/
│  │  ├─ state.py
│  │  ├─ graph.py
│  │  └─ nodes/
│  │     ├─ ingest_assets.py
│  │     ├─ analyze_product.py
│  │     ├─ plan_shots.py
│  │     ├─ generate_copy.py
│  │     ├─ generate_layout.py
│  │     ├─ build_prompts.py
│  │     ├─ render_images.py
│  │     ├─ overlay_text.py
│  │     ├─ run_qc.py
│  │     └─ finalize.py
│  │
│  ├─ ui/
│  │  ├─ pages/
│  │  │  ├─ home.py
│  │  │  ├─ task_form.py
│  │  │  └─ result_view.py
│  │  ├─ components/
│  │  │  ├─ upload_panel.py
│  │  │  ├─ preview_grid.py
│  │  │  └─ download_panel.py
│  │  └─ state.py
│  │
│  └─ utils/
│     ├─ json_repair.py
│     ├─ image_hash.py
│     ├─ file_utils.py
│     └─ time_utils.py
│
├─ assets/
│  ├─ fonts/
│  ├─ brand_refs/
│  └─ demo_inputs/
│
├─ outputs/
│  ├─ tasks/
│  ├─ previews/
│  └─ exports/
│
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ fixtures/
│
└─ docs/
   ├─ architecture.md
   ├─ prompts.md
   ├─ workflow.md
   └─ qa-rules.md