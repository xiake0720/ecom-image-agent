import { http, resolveApiUrl } from "./http";
import type { ApiEnvelope, TaskRuntimePayload, TaskSummary } from "../types/api";

/** 获取任务列表，供任务记录页复用。 */
export async function fetchTasks(): Promise<TaskSummary[]> {
  const resp = await http.get<ApiEnvelope<TaskSummary[]>>("/tasks");
  return resp.data.data.map((item) => ({
    ...item,
    export_zip_path: resolveApiUrl(item.export_zip_path),
  }));
}

/** 获取单任务摘要。 */
export async function fetchTask(taskId: string): Promise<TaskSummary> {
  const resp = await http.get<ApiEnvelope<TaskSummary>>(`/tasks/${taskId}`);
  return {
    ...resp.data.data,
    export_zip_path: resolveApiUrl(resp.data.data.export_zip_path),
  };
}

/** 获取任务运行时视图，供主图工作台轮询。 */
export async function fetchTaskRuntime(taskId: string): Promise<TaskRuntimePayload> {
  const resp = await http.get<ApiEnvelope<TaskRuntimePayload>>(`/tasks/${taskId}/runtime`);
  const payload = resp.data.data;
  return {
    ...payload,
    export_zip_url: resolveApiUrl(payload.export_zip_url),
    full_bundle_zip_url: resolveApiUrl(payload.full_bundle_zip_url),
    results: payload.results.map((item) => ({
      ...item,
      image_url: resolveApiUrl(item.image_url),
    })),
  };
}
