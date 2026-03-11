# QA Rules

- Verify generated output dimensions.
- Verify Pillow-rendered text stays inside the configured block.
- Attempt OCR readback when PaddleOCR runtime is available.
- Mark the task as `review_required` when a required check fails.

