# Workflow

The current workflow runs these nodes in order:

1. `ingest_assets`
2. `analyze_product`
3. `plan_shots`
4. `generate_copy`
5. `generate_layout`
6. `build_prompts`
7. `render_images`
8. `overlay_text`
9. `run_qc`
10. `finalize`

Each task persists source files, structured JSON artifacts, final images, previews, and a zip export under `outputs/tasks/{task_id}/`.

The current runnable version is mock-only. The workflow keeps stable node contracts and local artifact persistence, but does not call real Gemini, PaddleOCR, rembg, databases, or cloud services yet.
