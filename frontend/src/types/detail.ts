export type DetailTaskStatus = "created" | "running" | "completed" | "review_required" | "failed";
export type DetailRenderStatus = "queued" | "running" | "completed" | "failed";
export type DetailQCStatus = "passed" | "warning" | "failed";

export type DetailAssetRole =
  | "main_result"
  | "packaging"
  | "dry_leaf"
  | "tea_soup"
  | "leaf_bottom"
  | "scene_ref"
  | "bg_ref";

export interface DetailPageAssetRef {
  asset_id: string;
  role: DetailAssetRole;
  file_name: string;
  relative_path: string;
  source_type: string;
  source_task_id: string;
  source_result_file: string;
  width: number | null;
  height: number | null;
}

export interface DetailPagePlanScreen {
  screen_id: string;
  theme: string;
  goal: string;
  screen_type: "visual" | "info";
  suggested_asset_roles: DetailAssetRole[];
}

export interface DetailPagePlanPage {
  page_id: string;
  title: string;
  style_anchor: string;
  narrative_position: number;
  screens: DetailPagePlanScreen[];
}

export interface DetailPagePlanPayload {
  template_name: string;
  category: string;
  platform: string;
  style_preset: string;
  global_style_anchor: string;
  narrative: string[];
  total_screens: number;
  total_pages: number;
  pages: DetailPagePlanPage[];
}

export interface DetailPageCopyBlock {
  page_id: string;
  screen_id: string;
  headline: string;
  subheadline: string;
  selling_points: string[];
  body_copy: string;
  parameter_copy: string;
  cta_copy: string;
  notes: string;
}

export interface DetailPagePromptPlanItem {
  page_id: string;
  page_title: string;
  global_style_anchor: string;
  screen_themes: string[];
  layout_notes: string[];
  prompt: string;
  negative_prompt: string;
  references: DetailPageAssetRef[];
  target_aspect_ratio: string;
  target_width: number;
  target_height: number;
}

export interface DetailPageRenderResult {
  render_id: string;
  page_id: string;
  page_title: string;
  status: DetailRenderStatus;
  file_name: string;
  relative_path: string;
  width: number | null;
  height: number | null;
  reference_roles: string[];
  provider_name: string;
  model_name: string;
  error_message: string;
  started_at: string;
  completed_at: string;
}

export interface DetailPageQCCheck {
  check_id: string;
  check_name: string;
  page_id: string;
  status: DetailQCStatus;
  message: string;
  details: Record<string, unknown>;
}

export interface DetailPageQCPageSummary {
  page_id: string;
  title: string;
  status: DetailQCStatus;
  issues: string[];
  reference_roles: string[];
  file_name: string;
  width: number | null;
  height: number | null;
}

export interface DetailPageQCSummary {
  passed: boolean;
  review_required: boolean;
  warning_count: number;
  failed_count: number;
  issues: string[];
  checks: DetailPageQCCheck[];
  pages: DetailPageQCPageSummary[];
}

export interface DetailPageRuntimeImage {
  image_id: string;
  page_id: string;
  title: string;
  status: DetailRenderStatus;
  file_name: string;
  image_url: string;
  width: number | null;
  height: number | null;
  reference_roles: string[];
  error_message: string;
}

export interface DetailPageRuntimePayload {
  task_id: string;
  status: DetailTaskStatus;
  progress_percent: number;
  current_stage: string;
  current_stage_label: string;
  message: string;
  error_message: string;
  generated_count: number;
  planned_count: number;
  plan: DetailPagePlanPayload | null;
  copy_blocks: DetailPageCopyBlock[];
  prompt_plan: DetailPagePromptPlanItem[];
  qc_summary: DetailPageQCSummary;
  images: DetailPageRuntimeImage[];
  export_zip_url: string;
}

export interface DetailJobCreateResult {
  task_id: string;
  status: DetailTaskStatus;
}
