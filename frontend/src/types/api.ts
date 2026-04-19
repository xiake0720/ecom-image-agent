/**
 * 统一 API 类型定义。
 * 作用：让页面、hooks 和 service 都依赖同一份 contract，避免散落的字段猜测。
 */
export interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
  requestId: string;
}

export type TaskStatus = "created" | "running" | "completed" | "review_required" | "failed";
export type RuntimeResultStatus = "queued" | "running" | "completed" | "failed";
export type DbTaskType = "main_image" | "detail_page" | "image_edit";
export type DbTaskStatus = "pending" | "queued" | "running" | "succeeded" | "failed" | "partial_failed" | "cancelled";

export interface TaskSummary {
  task_id: string;
  task_type: string;
  status: TaskStatus;
  created_at: string;
  updated_at: string;
  title: string;
  platform: string;
  result_path: string;
  progress_percent: number;
  current_step: string;
  current_step_label: string;
  result_count_completed: number;
  result_count_total: number;
  export_zip_path: string;
  provider_label: string;
  model_label: string;
  detail_image_count: number;
  background_image_count: number;
}

export interface TaskRuntimeResult {
  id: string;
  title: string;
  subtitle: string;
  status: RuntimeResultStatus;
  image_url: string;
  file_name: string;
  width: number | null;
  height: number | null;
  generated_at: string;
}

export interface TaskRuntimeQCSummary {
  passed: boolean;
  review_required: boolean;
  warning_count: number;
  failed_count: number;
}

export interface TaskRuntimePayload {
  task_id: string;
  status: TaskStatus;
  progress_percent: number;
  current_step: string;
  current_step_label: string;
  message: string;
  queue_position: number | null;
  queue_size: number;
  provider_label: string;
  model_label: string;
  detail_image_count: number;
  background_image_count: number;
  result_count_completed: number;
  result_count_total: number;
  export_zip_url: string;
  full_bundle_zip_url: string;
  qc_summary: TaskRuntimeQCSummary;
  results: TaskRuntimeResult[];
}

export interface MainImageSubmitPayload {
  whiteBg: File;
  detailFiles: File[];
  bgFiles: File[];
  brandName: string;
  productName: string;
  category: string;
  platform: string;
  styleType: string;
  styleNotes: string;
  shotCount: number;
  aspectRatio: string;
  imageSize: string;
}

export interface V1TaskListItem {
  task_id: string;
  task_type: DbTaskType;
  status: DbTaskStatus;
  title: string | null;
  platform: string | null;
  biz_id: string | null;
  current_step: string | null;
  progress_percent: number;
  result_count: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface V1TaskListResponse {
  items: V1TaskListItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface V1TaskDetail {
  task_id: string;
  task_type: DbTaskType;
  status: DbTaskStatus;
  title: string | null;
  platform: string | null;
  biz_id: string | null;
  source_task_id: string | null;
  parent_task_id: string | null;
  current_step: string | null;
  progress_percent: number;
  input_summary: Record<string, unknown> | null;
  params: Record<string, unknown> | null;
  runtime_snapshot: Record<string, unknown> | null;
  result_summary: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface V1TaskEvent {
  event_id: string;
  event_type: string;
  level: "info" | "warning" | "error";
  step: string | null;
  message: string;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface V1TaskRuntimeResponse {
  task: V1TaskDetail;
  runtime: Record<string, unknown> | null;
  events: V1TaskEvent[];
}

export interface V1TaskResult {
  result_id: string;
  result_type: string;
  page_no: number | null;
  shot_no: number | null;
  version_no: number;
  parent_result_id: string | null;
  status: string;
  cos_key: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  width: number | null;
  height: number | null;
  prompt_plan: Record<string, unknown> | null;
  prompt_final: Record<string, unknown> | null;
  render_meta: Record<string, unknown> | null;
  qc_status: string | null;
  qc_score: number | null;
  is_primary: boolean;
  file_url: string;
  download_url_api: string;
  created_at: string;
  updated_at: string;
}

export interface V1TaskResultsResponse {
  task_id: string;
  items: V1TaskResult[];
}

export interface ImageEditRectangleSelection {
  x: number;
  y: number;
  width: number;
  height: number;
  unit: "ratio";
}

export interface ImageEditCreateRequest {
  selection_type: "rectangle";
  selection: ImageEditRectangleSelection;
  instruction: string;
}

export interface V1ImageEdit {
  edit_id: string;
  source_result_id: string;
  edit_task_id: string;
  edited_result_id: string | null;
  selection_type: string;
  selection: Record<string, unknown>;
  instruction: string;
  mode: string;
  status: string;
  error_message: string | null;
  metadata: Record<string, unknown> | null;
  edited_result: V1TaskResult | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface V1ImageEditListResponse {
  source_result_id: string;
  items: V1ImageEdit[];
}
