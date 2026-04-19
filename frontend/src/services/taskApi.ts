import { http, resolveApiUrl } from "./http";
import type {
  ApiEnvelope,
  DbTaskStatus,
  DbTaskType,
  TaskRuntimePayload,
  TaskSummary,
  V1TaskListResponse,
  V1TaskResultsResponse,
  V1TaskRuntimeResponse,
} from "../types/api";

export interface FetchV1TasksParams {
  page?: number;
  pageSize?: number;
  taskType?: DbTaskType | "";
  status?: DbTaskStatus | "";
}

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

/** 分页查询当前用户的 v1 历史任务。 */
export async function fetchV1Tasks(params: FetchV1TasksParams = {}): Promise<V1TaskListResponse> {
  const resp = await http.get<ApiEnvelope<V1TaskListResponse>>("/v1/tasks", {
    params: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
      task_type: params.taskType || undefined,
      status: params.status || undefined,
    },
  });
  return resp.data.data;
}

/** 查询当前用户任务的 v1 runtime 聚合。 */
export async function fetchV1TaskRuntime(taskId: string): Promise<V1TaskRuntimeResponse> {
  const resp = await http.get<ApiEnvelope<V1TaskRuntimeResponse>>(`/v1/tasks/${taskId}/runtime`);
  return resp.data.data;
}

/** 查询当前用户任务的 v1 结果摘要。 */
export async function fetchV1TaskResults(taskId: string): Promise<V1TaskResultsResponse> {
  const resp = await http.get<ApiEnvelope<V1TaskResultsResponse>>(`/v1/tasks/${taskId}/results`);
  return {
    ...resp.data.data,
    items: resp.data.data.items.map((item) => ({
      ...item,
      file_url: resolveApiUrl(item.file_url),
      download_url_api: resolveApiUrl(item.download_url_api),
    })),
  };
}
