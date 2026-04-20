# Ecom Image Agent V1 Database Schema

This is the concise schema guide for the final v1 database shape. The detailed table document is `docs/database-schema-v1.md`; the executable SQL reference is `docs/database/ecom_image_schema_v1.sql`.

## Source Of Truth

- Alembic head: `20260420_04`
- ORM models: `backend/db/models/`
- PostgreSQL target: 16
- UUID policy: application-generated UUIDs, no `pgcrypto` dependency

## Final Decisions

- `users.status`: `active`, `disabled`, `suspended`.
- `idempotency_keys`: final unique key is `(user_id, request_key)` with constraint `uq_idempotency_keys_user_id_request_key`.
- `tasks.queued_at`: retained and added as nullable. Existing queued/running/terminal rows are backfilled from `created_at`.
- `tasks.idem_key`: not retained. Idempotency is represented by `idempotency_keys`; no task FK is introduced in v1.
- `task_assets.role` / `task_assets.source_type`: documented dictionaries, not database enum checks. The DB only enforces non-empty strings.
- `task_assets.metadata`, `task_usage_records.metadata`, `image_edits.metadata`: PostgreSQL column name is `metadata`; ORM attribute is `metadata_json` where needed.
- `image_edits`: final v1 shape uses `source_result_id`, `edit_task_id`, `edited_result_id`, `selection_type`, `selection`, `mode`, `metadata`.
- JSONB GIN indexes are added only for operational query/debug fields; response cache JSON is not indexed.

## Tables

- `users`
- `refresh_tokens`
- `audit_logs`
- `idempotency_keys`
- `tasks`
- `task_results`
- `task_assets`
- `task_events`
- `task_usage_records`
- `image_edits`

## Relationships

```text
users
  -> refresh_tokens
  -> audit_logs
  -> idempotency_keys
  -> tasks
       -> task_results
       -> task_assets
       -> task_events
       -> task_usage_records
       -> image_edits via edit_task_id

tasks.source_task_id -> tasks.id
tasks.parent_task_id -> tasks.id
task_results.parent_result_id -> task_results.id
task_assets.source_task_result_id -> task_results.id
image_edits.source_result_id -> task_results.id
image_edits.edited_result_id -> task_results.id
```

## Operational Notes

- `updated_at` is trigger-maintained for `users`, `refresh_tokens`, `tasks`, `task_results`, `task_assets`, and `image_edits`.
- Binary image data is not stored in PostgreSQL. The database stores object keys, local compatibility keys, hashes, size, MIME type, and dimensions.
- In local compatibility mode, `cos_key` can contain a task-relative path. In COS mode, it contains the real COS object key.
- `task_assets.role` current values include `white_bg`, `detail`, `background_style`, `product`, `other`, `packaging`, `dry_leaf`, `tea_soup`, `leaf_bottom`, `scene_ref`, `bg_ref`, `main_result`, `edit_source`, `edit_mask`, `edit_annotation`, and `generated_result`.
- `task_assets.source_type` current values include `upload`, `main_task`, `cos_presign`, `task_result`, `system_generated`, and `imported`.

## Phase 2 Closure Summary

- Added migration `20260420_04`.
- Added `tasks.queued_at`.
- Added missing range/non-negative checks.
- Added JSONB GIN indexes for audit/task/result/asset/event/usage/edit metadata.
- Replaced old schema documentation that had drifted from Alembic and ORM.
- Added PostgreSQL verification coverage via script and integration test.
