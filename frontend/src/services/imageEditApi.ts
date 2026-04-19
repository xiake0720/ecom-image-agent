import { http, resolveApiUrl } from "./http";
import type { ApiEnvelope, ImageEditCreateRequest, V1ImageEdit, V1ImageEditListResponse } from "../types/api";

function resolveEditUrls(edit: V1ImageEdit): V1ImageEdit {
  if (!edit.edited_result) {
    return edit;
  }
  return {
    ...edit,
    edited_result: {
      ...edit.edited_result,
      file_url: resolveApiUrl(edit.edited_result.file_url),
      download_url_api: resolveApiUrl(edit.edited_result.download_url_api),
    },
  };
}

export async function createImageEdit(resultId: string, payload: ImageEditCreateRequest): Promise<V1ImageEdit> {
  const resp = await http.post<ApiEnvelope<V1ImageEdit>>(`/v1/results/${resultId}/edits`, payload);
  return resolveEditUrls(resp.data.data);
}

export async function fetchImageEdits(resultId: string): Promise<V1ImageEditListResponse> {
  const resp = await http.get<ApiEnvelope<V1ImageEditListResponse>>(`/v1/results/${resultId}/edits`);
  return {
    ...resp.data.data,
    items: resp.data.data.items.map(resolveEditUrls),
  };
}
