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
