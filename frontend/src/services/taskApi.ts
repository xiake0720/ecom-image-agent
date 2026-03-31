import { http } from "./http";
import type { ApiEnvelope, TaskSummary } from "../types/api";

/** 获取任务列表，供任务记录页复用。 */
export async function fetchTasks(): Promise<TaskSummary[]> {
  const resp = await http.get<ApiEnvelope<TaskSummary[]>>("/tasks");
  return resp.data.data;
}
