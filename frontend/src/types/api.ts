/**
 * 统一 API 返回类型。
 * 设计原因：前端页面和 hooks 只需要依赖这一层，不必重复解析后端 envelope。
 */
export interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
  requestId: string;
}

export interface TaskSummary {
  task_id: string;
  task_type: string;
  status: string;
  created_at: string;
  updated_at: string;
  title: string;
  platform: string;
  result_path: string;
}
