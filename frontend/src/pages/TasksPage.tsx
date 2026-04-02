import { useNavigate } from "react-router-dom";
import { PageHeader } from "../components/common/PageHeader";
import { PageShell } from "../components/layout/PageShell";
import { useTasks } from "../hooks/useTasks";
import type { TaskSummary } from "../types/api";
import "./TasksPage.css";

const LOCAL_STORAGE_TASK_KEY = "main-image-active-task-id";

export function TasksPage() {
  const navigate = useNavigate();
  const { tasks, loading } = useTasks();

  function openInWorkbench(task: TaskSummary) {
    window.localStorage.setItem(LOCAL_STORAGE_TASK_KEY, task.task_id);
    navigate("/main-images");
  }

  return (
    <PageShell activeKey="tasks">
      <PageHeader title="历史任务" subtitle="任务摘要可回看、恢复到工作台并下载结果" />
      <div className="tasks-page" style={{ width: "100%", padding: 0 }}>
        {loading ? <p className="tasks-loading">加载中...</p> : null}
        <div className="tasks-list">
          {tasks.map((task) => (
            <article key={task.task_id} className="task-summary-card">
              <div className="task-summary-head"><div><h3>{task.title || "未命名任务"}</h3><p>{task.task_id}</p></div><span className={`task-status-chip task-status-${task.status}`}>{statusLabel(task.status)}</span></div>
              <div className="task-summary-grid"><div><span>进度</span><strong>{task.progress_percent}%</strong></div><div><span>步骤</span><strong>{task.current_step_label || "待开始"}</strong></div><div><span>结果</span><strong>{task.result_count_completed}/{task.result_count_total}</strong></div><div><span>平台</span><strong>{task.platform || "-"}</strong></div><div><span>模型</span><strong>{task.model_label || task.provider_label || "-"}</strong></div><div><span>参考图</span><strong>{task.detail_image_count} / 背景 {task.background_image_count}</strong></div></div>
              <div className="task-summary-actions"><button type="button" className="task-link-btn" onClick={() => openInWorkbench(task)}>打开工作台</button></div>
            </article>
          ))}
        </div>
      </div>
    </PageShell>
  );
}

function statusLabel(status: TaskSummary["status"]): string {
  if (status === "created") return "排队中";
  if (status === "running") return "生成中";
  if (status === "completed") return "已完成";
  if (status === "review_required") return "待复核";
  return "失败";
}
