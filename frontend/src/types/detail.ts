export type DetailTaskStatus = "created" | "running" | "completed" | "review_required" | "failed";
export type DetailRenderStatus = "queued" | "running" | "completed" | "failed";
export type DetailQCStatus = "passed" | "warning" | "failed";
export type DetailVisualReviewStatus = "passed" | "warning" | "failed";

export type DetailAssetRole =
  | "main_result"
  | "packaging"
  | "dry_leaf"
  | "tea_soup"
  | "leaf_bottom"
  | "scene_ref"
  | "bg_ref";

export type DetailPageRole =
  | "hero_opening"
  | "dry_leaf_evidence"
  | "tea_soup_evidence"
  | "parameter_and_closing"
  | "leaf_bottom_process_evidence"
  | "brand_trust"
  | "gift_openbox_portable"
  | "brewing_method_info"
  | "scene_value_story"
  | "packaging_structure_value"
  | "package_closeup_evidence"
  | "brand_closing";

export type DetailAssetStrategy =
  | "anchor_required"
  | "reference_preferred"
  | "ai_supplement_allowed"
  | "supplement_only";

export type DetailRetryStrategy =
  | "original_prompt_retry"
  | "text_density_reduction"
  | "reference_rebinding"
  | "packaging_emphasis"
  | "style_correction";

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
  asset_strategy: DetailAssetStrategy;
  anchor_roles: DetailAssetRole[];
  supplement_roles: DetailAssetRole[];
  allow_generated_supporting_materials: boolean;
  material_focus: string;
  notes: string[];
}

export interface DetailPagePlanPage {
  page_id: string;
  title: string;
  page_role: DetailPageRole;
  layout_mode: string;
  primary_headline_screen_id: string;
  style_anchor: string;
  narrative_position: number;
  asset_strategy: DetailAssetStrategy;
  anchor_roles: DetailAssetRole[];
  supplement_roles: DetailAssetRole[];
  allow_generated_supporting_materials: boolean;
  review_focus: string[];
  screens: DetailPagePlanScreen[];
}

export interface DetailPagePlanPayload {
  template_name: string;
  category: string;
  platform: string;
  style_preset: string;
  canvas_aspect_ratio: string;
  screens_per_page: number;
  layout_mode: string;
  global_style_anchor: string;
  narrative: string[];
  total_screens: number;
  total_pages: number;
  pages: DetailPagePlanPage[];
}

export interface DetailPageCopyBlock {
  page_id: string;
  screen_id: string;
  headline_level: "primary";
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
  page_role: DetailPageRole;
  layout_mode: string;
  primary_headline_screen_id: string;
  global_style_anchor: string;
  screen_themes: string[];
  layout_notes: string[];
  title_copy: string;
  subtitle_copy: string;
  selling_points_for_render: string[];
  prompt: string;
  negative_prompt: string;
  references: DetailPageAssetRef[];
  asset_strategy: DetailAssetStrategy;
  allow_generated_supporting_materials: boolean;
  copy_strategy: string;
  text_density: string;
  should_render_text: boolean;
  retryable: boolean;
  target_aspect_ratio: string;
  target_width: number;
  target_height: number;
}

export interface DetailPageRenderResult {
  render_id: string;
  page_id: string;
  page_title: string;
  page_role: DetailPageRole;
  status: DetailRenderStatus;
  file_name: string;
  relative_path: string;
  width: number | null;
  height: number | null;
  reference_roles: string[];
  provider_name: string;
  model_name: string;
  error_message: string;
  retry_count: number;
  retry_strategies: DetailRetryStrategy[];
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
  page_role: DetailPageRole;
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
  page_role: DetailPageRole;
  status: DetailRenderStatus;
  file_name: string;
  image_url: string;
  width: number | null;
  height: number | null;
  reference_roles: string[];
  error_message: string;
  retry_count: number;
}

export interface DetailPreflightRoleSummary {
  role: DetailAssetRole;
  count: number;
  file_names: string[];
}

export interface DetailPreflightReport {
  passed: boolean;
  warnings: string[];
  strong_anchor_roles: DetailAssetRole[];
  ai_supplement_roles: DetailAssetRole[];
  available_roles: DetailAssetRole[];
  missing_required_roles: DetailAssetRole[];
  missing_optional_roles: DetailAssetRole[];
  asset_summary: DetailPreflightRoleSummary[];
  recommended_page_roles: DetailPageRole[];
  notes: string[];
}

export interface DetailDirectorBrief {
  template_name: string;
  category: string;
  platform: string;
  style_preset: string;
  global_style_anchor: string;
  page_rhythm: string[];
  anchor_priority: DetailAssetRole[];
  required_page_roles: DetailPageRole[];
  optional_page_roles: DetailPageRole[];
  ai_supplement_page_roles: DetailPageRole[];
  planning_notes: string[];
  material_notes: string[];
  constraints: string[];
}

export interface DetailVisualReviewPage {
  page_id: string;
  page_role: DetailPageRole;
  title: string;
  status: DetailVisualReviewStatus;
  findings: string[];
  recommended_actions: string[];
}

export interface DetailVisualReviewReport {
  overall_status: DetailVisualReviewStatus;
  summary: string[];
  pages: DetailVisualReviewPage[];
}

export interface DetailRetryDecisionItem {
  page_id: string;
  page_role: DetailPageRole;
  should_retry: boolean;
  reason: string;
  strategies: DetailRetryStrategy[];
}

export interface DetailRetryDecisionReport {
  pages: DetailRetryDecisionItem[];
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
  preflight_report: DetailPreflightReport | null;
  director_brief: DetailDirectorBrief | null;
  visual_review: DetailVisualReviewReport | null;
  retry_decisions: DetailRetryDecisionReport | null;
  qc_summary: DetailPageQCSummary;
  images: DetailPageRuntimeImage[];
  export_zip_url: string;
}

export interface DetailJobCreateResult {
  task_id: string;
  status: DetailTaskStatus;
}
