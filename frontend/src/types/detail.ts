export type DetailTaskStatus = "created" | "running" | "completed" | "review_required" | "failed";

export interface DetailPageAssetRef {
  asset_id: string;
  role: string;
  file_name: string;
  relative_path: string;
  source_type: string;
  source_task_id: string;
  source_result_file: string;
}

export interface DetailPagePlanScreen {
  screen_id: string;
  theme: string;
  goal: string;
  screen_type: "visual" | "info";
  suggested_asset_roles: string[];
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
}

export interface DetailPageRuntimeImage {
  image_id: string;
  page_id: string;
  title: string;
  status: "queued" | "running" | "completed" | "failed";
  file_name: string;
  image_url: string;
  width: number | null;
  height: number | null;
  reference_roles: string[];
}

export interface DetailPageQCSummary {
  passed: boolean;
  warning_count: number;
  failed_count: number;
  issues: string[];
}

export interface DetailPageRuntimePayload {
  task_id: string;
  status: DetailTaskStatus;
  progress_percent: number;
  current_stage: string;
  current_stage_label: string;
  message: string;
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
  status: string;
}
