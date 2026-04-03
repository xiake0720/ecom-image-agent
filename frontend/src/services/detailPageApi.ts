import { http, resolveApiUrl } from "./http";
import type { ApiEnvelope, TaskSummary } from "../types/api";
import type { DetailJobCreateResult, DetailPageRuntimePayload } from "../types/detail";

export interface DetailJobSubmitPayload {
  mode: "plan" | "full";
  brandName: string;
  productName: string;
  teaType: string;
  platform: string;
  stylePreset: string;
  priceBand: string;
  targetSliceCount: number;
  imageSize: string;
  mainImageTaskId: string;
  selectedMainResultIds: string[];
  sellingPoints: string[];
  specs: Record<string, string>;
  styleNotes: string;
  brewSuggestion: string;
  extraRequirements: string;
  preferMainResultFirst: boolean;
  packagingFiles: File[];
  dryLeafFiles: File[];
  teaSoupFiles: File[];
  leafBottomFiles: File[];
  sceneRefFiles: File[];
  bgRefFiles: File[];
}

/** 提交详情图任务，支持仅规划或完整生成。 */
export async function submitDetailJob(payload: DetailJobSubmitPayload): Promise<DetailJobCreateResult> {
  const form = new FormData();
  payload.packagingFiles.forEach((file) => form.append("packaging_files", file));
  payload.dryLeafFiles.forEach((file) => form.append("dry_leaf_files", file));
  payload.teaSoupFiles.forEach((file) => form.append("tea_soup_files", file));
  payload.leafBottomFiles.forEach((file) => form.append("leaf_bottom_files", file));
  payload.sceneRefFiles.forEach((file) => form.append("scene_ref_files", file));
  payload.bgRefFiles.forEach((file) => form.append("bg_ref_files", file));
  form.append("brand_name", payload.brandName);
  form.append("product_name", payload.productName);
  form.append("tea_type", payload.teaType);
  form.append("platform", payload.platform);
  form.append("style_preset", payload.stylePreset);
  form.append("price_band", payload.priceBand);
  form.append("target_slice_count", String(payload.targetSliceCount));
  form.append("image_size", payload.imageSize);
  form.append("main_image_task_id", payload.mainImageTaskId);
  form.append("selected_main_result_ids", JSON.stringify(payload.selectedMainResultIds));
  form.append("selling_points_json", JSON.stringify(payload.sellingPoints));
  form.append("specs_json", JSON.stringify(payload.specs));
  form.append("style_notes", payload.styleNotes);
  form.append("brew_suggestion", payload.brewSuggestion);
  form.append("extra_requirements", payload.extraRequirements);
  form.append("prefer_main_result_first", payload.preferMainResultFirst ? "true" : "false");

  const endpoint = payload.mode === "plan" ? "/detail/jobs/plan" : "/detail/jobs";
  const resp = await http.post<ApiEnvelope<DetailJobCreateResult>>(endpoint, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return resp.data.data;
}

/** 查询详情图 runtime。 */
export async function fetchDetailRuntime(taskId: string): Promise<DetailPageRuntimePayload> {
  const resp = await http.get<ApiEnvelope<DetailPageRuntimePayload>>(`/detail/jobs/${taskId}/runtime`);
  const payload = resp.data.data;
  return {
    ...payload,
    export_zip_url: payload.export_zip_url ? resolveApiUrl(payload.export_zip_url) : "",
    images: payload.images.map((item) => ({
      ...item,
      image_url: item.image_url ? resolveApiUrl(item.image_url) : "",
    })),
  };
}

/** 查询详情图任务摘要。 */
export async function fetchDetailTask(taskId: string): Promise<TaskSummary> {
  const resp = await http.get<ApiEnvelope<TaskSummary>>(`/detail/jobs/${taskId}`);
  return resp.data.data;
}

/** 构建详情图文件访问地址。 */
export function resolveDetailFileUrl(taskId: string, fileName: string): string {
  return resolveApiUrl(`/detail/jobs/${taskId}/files/${encodeURI(fileName)}`);
}
