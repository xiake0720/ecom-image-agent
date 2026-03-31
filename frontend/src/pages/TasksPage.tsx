import { useTasks } from "../hooks/useTasks";

export function TasksPage() {
  const { tasks, loading } = useTasks();
  return (
    <div>
      <h2>任务记录</h2>
      {loading ? <p>加载中...</p> : null}
      <ul>
        {tasks.map((task) => (
          <li key={task.task_id}>
            {task.task_id} | {task.task_type} | {task.status} | {task.title}
          </li>
        ))}
      </ul>
    </div>
  );
}
