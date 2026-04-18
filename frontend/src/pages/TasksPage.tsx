import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../components/common/PageHeader";
import { PageShell } from "../components/layout/PageShell";
import { useTasks } from "../hooks/useTasks";
import type { TaskSummary } from "../types/api";
import "./TasksPage.css";

const LOCAL_STORAGE_TASK_KEY = "main-image-active-task-id";
const SUPPORTED_TASK_TYPES = new Set<TaskSummary["task_type"]>(["main_image", "detail_page_v2"]);

export function TasksPage() {
  const navigate = useNavigate();
  const { tasks, loading } = useTasks();

  const activeTasks = useMemo(() => tasks.filter((task) => SUPPORTED_TASK_TYPES.has(task.task_type)), [tasks]);
  const deprecatedTasks = useMemo(() => tasks.filter((task) => !SUPPORTED_TASK_TYPES.has(task.task_type)), [tasks]);

  function openTask(task: TaskSummary) {
    if (task.task_type === "main_image") {
      window.localStorage.setItem(LOCAL_STORAGE_TASK_KEY, task.task_id);
      navigate("/main-images");
      return;
    }

    if (task.task_type === "detail_page_v2") {
      navigate(`/detail-pages?task_id=${encodeURIComponent(task.task_id)}`);
    }
  }

  return (
    <PageShell activeKey="tasks">
      <PageHeader title="历史任务" subtitle="一期仅保留主图任务与 detail v2 任务回看；旧详情页任务保留索引但不再作为正式入口。" />
      <div className="tasks-page" style={{ width: "100%", padding: 0 }}>
        {loading ? <p className="tasks-loading">加载中...</p> : null}

        {!loading && activeTasks.length === 0 ? <p className="tasks-empty">当前没有可回看的 v1 正式任务。</p> : null}

        {activeTasks.length > 0 ? (
          <section className="tasks-section">
            <div className="tasks-section-head">
              <div>
                <h2>正式任务</h2>
                <p>支持打开主图工作台或详情图工作台查看 runtime、结果图与下载入口。</p>
              </div>
              <span className="tasks-page-metric">{activeTasks.length} 条</span>
            </div>
            <div className="tasks-list">
              {activeTasks.map((task) => (
                <article key={task.task_id} className="task-summary-card">
                  <div className="task-summary-head">
                    <div>
                      <h3>{task.title || "未命名任务"}</h3>
                      <p>{task.task_id}</p>
                    </div>
                    <div className="task-summary-tag-group">
                      <span className={`task-type-chip task-type-${task.task_type}`}>{taskTypeLabel(task.task_type)}</span>
                      <span className={`task-status-chip task-status-${task.status}`}>{statusLabel(task.status)}</span>
                    </div>
                  </div>
                  <div className="task-summary-grid">
                    <div>
                      <span>进度</span>
                      <strong>{task.progress_percent}%</strong>
                    </div>
                    <div>
                      <span>阶段</span>
                      <strong>{task.current_step_label || "待开始"}</strong>
                    </div>
                    <div>
                      <span>结果</span>
                      <strong>
                        {task.result_count_completed}/{task.result_count_total}
                      </strong>
                    </div>
                    <div>
                      <span>平台</span>
                      <strong>{task.platform || "-"}</strong>
                    </div>
                    <div>
                      <span>模型</span>
                      <strong>{task.model_label || task.provider_label || "-"}</strong>
                    </div>
                    <div>
                      <span>参考图</span>
                      <strong>
                        {task.detail_image_count} / 背景 {task.background_image_count}
                      </strong>
                    </div>
                  </div>
                  <div className="task-summary-actions">
                    <button type="button" className="task-link-btn" onClick={() => openTask(task)}>
                      {openButtonLabel(task.task_type)}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {deprecatedTasks.length > 0 ? (
          <section className="tasks-section tasks-section-deprecated">
            <div className="tasks-section-head">
              <div>
                <h2>Deprecated 任务</h2>
                <p>以下索引来自旧详情页模块化实现，仅保留历史记录，不再纳入一期正式入口。</p>
              </div>
              <span className="tasks-page-metric">{deprecatedTasks.length} 条</span>
            </div>
            <div className="tasks-list">
              {deprecatedTasks.map((task) => (
                <article key={task.task_id} className="task-summary-card">
                  <div className="task-summary-head">
                    <div>
                      <h3>{task.title || "未命名旧任务"}</h3>
                      <p>{task.task_id}</p>
                    </div>
                    <div className="task-summary-tag-group">
                      <span className="task-type-chip task-type-legacy">{taskTypeLabel(task.task_type)}</span>
                      <span className={`task-status-chip task-status-${task.status}`}>{statusLabel(task.status)}</span>
                    </div>
                  </div>
                  <p className="task-summary-note">
                    该任务来自已冻结的旧实现，当前正式工作台不再承接查看与继续编辑。
                  </p>
                  <div className="task-summary-actions">
                    <button type="button" className="task-link-btn" disabled>
                      旧版任务已冻结
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </PageShell>
  );
}

function openButtonLabel(taskType: TaskSummary["task_type"]): string {
  if (taskType === "detail_page_v2") {
    return "查看详情图任务";
  }
  return "打开主图工作台";
}

function taskTypeLabel(taskType: TaskSummary["task_type"]): string {
  if (taskType === "main_image") return "主图任务";
  if (taskType === "detail_page_v2") return "详情图 V2";
  if (taskType === "detail_page") return "旧详情页";
  return taskType;
}

function statusLabel(status: TaskSummary["status"]): string {
  if (status === "created") return "排队中";
  if (status === "running") return "生成中";
  if (status === "completed") return "已完成";
  if (status === "review_required") return "待复核";
  return "失败";
}
