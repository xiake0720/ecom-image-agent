import { useEffect, useState } from "react";
import type { TaskSummary } from "../types/api";
import { fetchTasks } from "../services/taskApi";

/**
 * 任务列表 Hook。
 * 为什么封装：避免页面组件直接处理加载状态与异常，提升可复用性。
 */
export function useTasks() {
  const [tasks, setTasks] = useState<TaskSummary[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchTasks()
      .then(setTasks)
      .finally(() => setLoading(false));
  }, []);

  return { tasks, loading };
}
