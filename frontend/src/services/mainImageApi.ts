import { http } from "./http";
import type { ApiEnvelope, MainImageSubmitPayload, TaskSummary } from "../types/api";

/**
 * 提交主图生成任务。
 * 说明：页面只负责收集状态，真正的 multipart 组装集中放在 service 层。
 */
export async function submitMainImageTask(payload: MainImageSubmitPayload): Promise<TaskSummary> {
  const form = new FormData();
  form.append("white_bg", payload.whiteBg);
  payload.detailFiles.forEach((file) => form.append("detail_files", file));
  payload.bgFiles.forEach((file) => form.append("bg_files", file));
  form.append("brand_name", payload.brandName);
  form.append("product_name", payload.productName);
  form.append("category", payload.category);
  form.append("platform", payload.platform);
  form.append("style_type", payload.styleType);
  form.append("style_notes", payload.styleNotes);
  form.append("shot_count", String(payload.shotCount));
  form.append("aspect_ratio", payload.aspectRatio);
  form.append("image_size", payload.imageSize);

  const resp = await http.post<ApiEnvelope<TaskSummary>>("/image/generate-main", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return resp.data.data;
}
