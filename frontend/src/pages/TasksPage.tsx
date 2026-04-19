import { type PointerEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../components/common/PageHeader";
import { PageShell } from "../components/layout/PageShell";
import { extractApiErrorMessage } from "../services/apiError";
import { createImageEdit, fetchImageEdits } from "../services/imageEditApi";
import { fetchFileDownloadUrl } from "../services/storageApi";
import { fetchV1TaskResults, fetchV1TaskRuntime, fetchV1Tasks } from "../services/taskApi";
import type {
  DbTaskStatus,
  DbTaskType,
  ImageEditRectangleSelection,
  V1ImageEdit,
  V1TaskListItem,
  V1TaskResult,
  V1TaskResultsResponse,
  V1TaskRuntimeResponse,
} from "../types/api";
import "./TasksPage.css";

const LOCAL_STORAGE_TASK_KEY = "main-image-active-task-id";
const PAGE_SIZE = 10;

const TASK_TYPE_OPTIONS: Array<{ value: DbTaskType | ""; label: string }> = [
  { value: "", label: "全部类型" },
  { value: "main_image", label: "主图任务" },
  { value: "detail_page", label: "详情图任务" },
  { value: "image_edit", label: "图片编辑" },
];

const STATUS_OPTIONS: Array<{ value: DbTaskStatus | ""; label: string }> = [
  { value: "", label: "全部状态" },
  { value: "pending", label: "待创建" },
  { value: "queued", label: "排队中" },
  { value: "running", label: "运行中" },
  { value: "succeeded", label: "已成功" },
  { value: "partial_failed", label: "部分失败" },
  { value: "failed", label: "已失败" },
  { value: "cancelled", label: "已取消" },
];

export function TasksPage() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<V1TaskListItem[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [taskType, setTaskType] = useState<DbTaskType | "">("");
  const [status, setStatus] = useState<DbTaskStatus | "">("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [runtime, setRuntime] = useState<V1TaskRuntimeResponse | null>(null);
  const [results, setResults] = useState<V1TaskResultsResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [detailRefreshToken, setDetailRefreshToken] = useState(0);
  const [listRefreshToken, setListRefreshToken] = useState(0);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const selectedTask = useMemo(() => tasks.find((item) => item.task_id === selectedTaskId) ?? null, [selectedTaskId, tasks]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErrorMessage("");

    fetchV1Tasks({ page, pageSize: PAGE_SIZE, taskType, status })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setTasks(payload.items);
        setTotal(payload.total);
        setSelectedTaskId((current) => {
          if (current && payload.items.some((item) => item.task_id === current)) {
            return current;
          }
          return payload.items[0]?.task_id ?? "";
        });
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorMessage(extractApiErrorMessage(error));
          setTasks([]);
          setTotal(0);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [listRefreshToken, page, status, taskType]);

  useEffect(() => {
    if (!selectedTaskId) {
      setRuntime(null);
      setResults(null);
      return;
    }

    let cancelled = false;
    setDetailLoading(true);
    setDetailError("");

    Promise.all([fetchV1TaskRuntime(selectedTaskId), fetchV1TaskResults(selectedTaskId)])
      .then(([runtimePayload, resultsPayload]) => {
        if (cancelled) {
          return;
        }
        setRuntime(runtimePayload);
        setResults(resultsPayload);
      })
      .catch((error) => {
        if (!cancelled) {
          setRuntime(null);
          setResults(null);
          setDetailError(extractApiErrorMessage(error));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDetailLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [detailRefreshToken, selectedTaskId]);

  function updateTaskType(next: DbTaskType | "") {
    setTaskType(next);
    setPage(1);
  }

  function updateStatus(next: DbTaskStatus | "") {
    setStatus(next);
    setPage(1);
  }

  function openTask(task: V1TaskListItem) {
    if (task.task_type === "main_image") {
      window.localStorage.setItem(LOCAL_STORAGE_TASK_KEY, task.task_id);
      navigate("/main-images");
      return;
    }

    if (task.task_type === "detail_page") {
      navigate(`/detail-pages?task_id=${encodeURIComponent(task.task_id)}`);
      return;
    }

    if (task.task_type === "image_edit") {
      setSelectedTaskId(task.task_id);
    }
  }

  async function downloadResult(result: V1TaskResult) {
    try {
      const signed = await fetchFileDownloadUrl(result.result_id);
      window.open(signed.download_url, "_blank", "noopener,noreferrer");
    } catch {
      if (result.file_url) {
        window.open(result.file_url, "_blank", "noopener,noreferrer");
      }
    }
  }

  function refreshSelectedTaskDetail() {
    setListRefreshToken((current) => current + 1);
    setDetailRefreshToken((current) => current + 1);
  }

  return (
    <PageShell activeKey="tasks">
      <PageHeader
        title="历史任务"
        subtitle="当前页面已接入 /api/v1/tasks，任务列表、runtime、结果摘要均按当前登录用户隔离。"
        actions={
          <div className="tasks-filter-bar">
            <select value={taskType} onChange={(event) => updateTaskType(event.target.value as DbTaskType | "")}>
              {TASK_TYPE_OPTIONS.map((item) => (
                <option key={item.value || "all"} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
            <select value={status} onChange={(event) => updateStatus(event.target.value as DbTaskStatus | "")}>
              {STATUS_OPTIONS.map((item) => (
                <option key={item.value || "all"} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
        }
      />

      <div className="tasks-page">
        <section className="tasks-list-panel">
          <div className="tasks-section-head">
            <div>
              <h2>任务列表</h2>
              <p>共 {total} 条，当前第 {page} / {pageCount} 页。</p>
            </div>
            <button
              type="button"
              className="task-link-btn"
              onClick={() => {
                setPage(1);
                setListRefreshToken((current) => current + 1);
              }}
              disabled={loading}
            >
              刷新
            </button>
          </div>

          {loading ? <p className="tasks-loading">加载中...</p> : null}
          {errorMessage ? <p className="tasks-error">{errorMessage}</p> : null}
          {!loading && !errorMessage && tasks.length === 0 ? <p className="tasks-empty">当前筛选条件下没有任务。</p> : null}

          <div className="tasks-list">
            {tasks.map((task) => (
              <article
                key={task.task_id}
                className={`task-summary-card ${selectedTaskId === task.task_id ? "task-summary-card-active" : ""}`}
              >
                <button type="button" className="task-card-select" onClick={() => setSelectedTaskId(task.task_id)}>
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
                      <strong>{formatPercent(task.progress_percent)}</strong>
                    </div>
                    <div>
                      <span>阶段</span>
                      <strong>{task.current_step || "待开始"}</strong>
                    </div>
                    <div>
                      <span>结果</span>
                      <strong>{task.result_count}</strong>
                    </div>
                    <div>
                      <span>平台</span>
                      <strong>{task.platform || "-"}</strong>
                    </div>
                    <div>
                      <span>创建时间</span>
                      <strong>{formatDate(task.created_at)}</strong>
                    </div>
                    <div>
                      <span>更新时间</span>
                      <strong>{formatDate(task.updated_at)}</strong>
                    </div>
                  </div>
                </button>
                <div className="task-summary-actions">
                  <button type="button" className="task-link-btn" onClick={() => openTask(task)} disabled={!canOpenTask(task)}>
                    {openButtonLabel(task.task_type)}
                  </button>
                </div>
              </article>
            ))}
          </div>

          <div className="tasks-pagination">
            <button type="button" className="task-link-btn" disabled={page <= 1 || loading} onClick={() => setPage((current) => Math.max(1, current - 1))}>
              上一页
            </button>
            <span>{page} / {pageCount}</span>
            <button type="button" className="task-link-btn" disabled={page >= pageCount || loading} onClick={() => setPage((current) => current + 1)}>
              下一页
            </button>
          </div>
        </section>

        <aside className="tasks-detail-panel">
          <TaskDetailPanel
            task={selectedTask}
            runtime={runtime}
            results={results}
            loading={detailLoading}
            errorMessage={detailError}
            onDownload={downloadResult}
            onEditCreated={refreshSelectedTaskDetail}
          />
        </aside>
      </div>
    </PageShell>
  );
}

interface TaskDetailPanelProps {
  task: V1TaskListItem | null;
  runtime: V1TaskRuntimeResponse | null;
  results: V1TaskResultsResponse | null;
  loading: boolean;
  errorMessage: string;
  onDownload: (result: V1TaskResult) => void;
  onEditCreated: () => void;
}

function TaskDetailPanel({ task, runtime, results, loading, errorMessage, onDownload, onEditCreated }: TaskDetailPanelProps) {
  const [editingResultId, setEditingResultId] = useState("");

  if (!task) {
    return (
      <div className="task-detail-card">
        <h2>任务详情</h2>
        <p className="tasks-empty">请选择左侧任务。</p>
      </div>
    );
  }

  return (
    <div className="task-detail-card">
      <div className="tasks-section-head">
        <div>
          <h2>任务详情</h2>
          <p>{task.task_id}</p>
        </div>
        <span className={`task-status-chip task-status-${task.status}`}>{statusLabel(task.status)}</span>
      </div>

      {loading ? <p className="tasks-loading">正在读取 runtime 和结果...</p> : null}
      {errorMessage ? <p className="tasks-error">{errorMessage}</p> : null}

      <div className="task-detail-grid">
        <div>
          <span>类型</span>
          <strong>{taskTypeLabel(task.task_type)}</strong>
        </div>
        <div>
          <span>进度</span>
          <strong>{formatPercent(runtime?.task.progress_percent ?? task.progress_percent)}</strong>
        </div>
        <div>
          <span>当前阶段</span>
          <strong>{runtime?.task.current_step || task.current_step || "-"}</strong>
        </div>
        <div>
          <span>重试次数</span>
          <strong>{runtime?.task.retry_count ?? 0}</strong>
        </div>
      </div>

      {runtime?.task.error_message ? <p className="tasks-error">{runtime.task.error_message}</p> : null}

      <section className="task-detail-section">
        <h3>运行事件</h3>
        {runtime?.events.length ? (
          <div className="task-events-list">
            {runtime.events.slice().reverse().map((event) => (
              <article key={event.event_id} className={`task-event-item task-event-${event.level}`}>
                <strong>{event.message}</strong>
                <span>{event.event_type} / {event.step || "-"}</span>
                <small>{formatDate(event.created_at)}</small>
              </article>
            ))}
          </div>
        ) : (
          <p className="tasks-empty">暂无事件。</p>
        )}
      </section>

      <section className="task-detail-section">
        <h3>结果摘要</h3>
        {results?.items.length ? (
          <div className="task-results-grid">
            {results.items.map((result) => (
              <article key={result.result_id} className="task-result-card">
                {result.file_url && result.mime_type.startsWith("image/") ? (
                  <img src={result.file_url} alt={result.cos_key} />
                ) : (
                  <div className="task-result-placeholder">无本地预览</div>
                )}
                <div>
                  <strong>{result.result_type}</strong>
                  <span className="task-result-version">v{result.version_no}</span>
                  <p>{result.width && result.height ? `${result.width} x ${result.height}` : result.mime_type}</p>
                  <button type="button" className="task-link-btn" onClick={() => onDownload(result)}>
                    下载
                  </button>
                  {result.mime_type.startsWith("image/") ? (
                    <button
                      type="button"
                      className="task-link-btn task-edit-btn"
                      onClick={() => setEditingResultId((current) => (current === result.result_id ? "" : result.result_id))}
                    >
                      {editingResultId === result.result_id ? "收起编辑" : "局部编辑"}
                    </button>
                  ) : null}
                </div>
                {editingResultId === result.result_id ? (
                  <ImageEditPanel result={result} onEditCreated={onEditCreated} />
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <p className="tasks-empty">暂无结果。</p>
        )}
      </section>
    </div>
  );
}

interface ImageEditPanelProps {
  result: V1TaskResult;
  onEditCreated: () => void;
}

const EDIT_INSTRUCTION_EXAMPLES = [
  "修改选区内的局部文案，保持整体风格一致",
  "优化这个区域的视觉层次，让卖点更清晰",
  "保留主体，仅调整选中区域的背景和光影",
];

function ImageEditPanel({ result, onEditCreated }: ImageEditPanelProps) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const dragStartRef = useRef<{ x: number; y: number } | null>(null);
  const [selection, setSelection] = useState<ImageEditRectangleSelection>({
    x: 0.18,
    y: 0.18,
    width: 0.36,
    height: 0.3,
    unit: "ratio",
  });
  const [instruction, setInstruction] = useState("");
  const [edits, setEdits] = useState<V1ImageEdit[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setHistoryLoading(true);
    setErrorMessage("");
    fetchImageEdits(result.result_id)
      .then((payload) => {
        if (!cancelled) {
          setEdits(payload.items);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setErrorMessage(extractApiErrorMessage(error));
          setEdits([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setHistoryLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [refreshToken, result.result_id]);

  const hasValidSelection = selection.width >= 0.02 && selection.height >= 0.02;

  function readPointerPoint(event: PointerEvent<HTMLDivElement>) {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect || rect.width <= 0 || rect.height <= 0) {
      return null;
    }
    return {
      x: clamp((event.clientX - rect.left) / rect.width, 0, 1),
      y: clamp((event.clientY - rect.top) / rect.height, 0, 1),
    };
  }

  function startSelection(event: PointerEvent<HTMLDivElement>) {
    const point = readPointerPoint(event);
    if (!point) {
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    dragStartRef.current = point;
    setSelection({ x: point.x, y: point.y, width: 0.001, height: 0.001, unit: "ratio" });
  }

  function moveSelection(event: PointerEvent<HTMLDivElement>) {
    const start = dragStartRef.current;
    const point = readPointerPoint(event);
    if (!start || !point) {
      return;
    }
    setSelection(normalizeSelection(start, point));
  }

  function endSelection(event: PointerEvent<HTMLDivElement>) {
    dragStartRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  async function submitEdit() {
    const trimmed = instruction.trim();
    if (!hasValidSelection) {
      setErrorMessage("请先在图片上框选需要编辑的区域。");
      return;
    }
    if (!trimmed) {
      setErrorMessage("请输入编辑指令。");
      return;
    }
    setSubmitting(true);
    setErrorMessage("");
    try {
      await createImageEdit(result.result_id, {
        selection_type: "rectangle",
        selection,
        instruction: trimmed,
      });
      setInstruction("");
      setRefreshToken((current) => current + 1);
      onEditCreated();
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="image-edit-panel">
      <div className="image-edit-head">
        <div>
          <strong>局部二次生成</strong>
          <p>拖拽矩形选区，输入指令后生成派生版本。</p>
        </div>
        <span>{formatSelection(selection)}</span>
      </div>

      <div
        ref={canvasRef}
        className="image-edit-canvas"
        onPointerDown={startSelection}
        onPointerMove={moveSelection}
        onPointerUp={endSelection}
        onPointerCancel={endSelection}
      >
        {result.file_url ? <img src={result.file_url} alt={result.cos_key} draggable={false} /> : null}
        <div
          className="image-edit-selection"
          style={{
            left: `${selection.x * 100}%`,
            top: `${selection.y * 100}%`,
            width: `${selection.width * 100}%`,
            height: `${selection.height * 100}%`,
          }}
        />
      </div>

      <label className="image-edit-field" htmlFor={`image-edit-instruction-${result.result_id}`}>
        <span>编辑指令</span>
        <textarea
          id={`image-edit-instruction-${result.result_id}`}
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          placeholder="例如：保留主体，仅优化选中区域的文字和光影"
          rows={3}
        />
      </label>

      <div className="image-edit-examples">
        {EDIT_INSTRUCTION_EXAMPLES.map((example) => (
          <button key={example} type="button" onClick={() => setInstruction(example)}>
            {example}
          </button>
        ))}
      </div>

      {errorMessage ? <p className="tasks-error">{errorMessage}</p> : null}

      <div className="image-edit-actions">
        <button
          type="button"
          className="task-link-btn"
          onClick={() => setSelection({ x: 0.18, y: 0.18, width: 0.36, height: 0.3, unit: "ratio" })}
        >
          重置选区
        </button>
        <button type="button" className="task-link-btn task-edit-submit" disabled={submitting} onClick={submitEdit}>
          {submitting ? "提交中..." : "提交编辑任务"}
        </button>
      </div>

      <div className="image-edit-history">
        <div className="image-edit-history-head">
          <strong>编辑历史</strong>
          <button type="button" className="task-link-btn" onClick={() => setRefreshToken((current) => current + 1)} disabled={historyLoading}>
            刷新
          </button>
        </div>
        {historyLoading ? <p className="tasks-loading">正在读取编辑历史...</p> : null}
        {!historyLoading && edits.length === 0 ? <p className="tasks-empty">暂无编辑记录。</p> : null}
        {edits.map((edit) => (
          <article key={edit.edit_id} className="image-edit-history-item">
            {edit.edited_result?.file_url ? <img src={edit.edited_result.file_url} alt={edit.edited_result.cos_key} /> : null}
            <div>
              <strong>{editStatusLabel(edit.status)} / {modeLabel(edit.mode)}</strong>
              <p>{edit.instruction}</p>
              <small>{formatDate(edit.created_at)} · task {edit.edit_task_id}</small>
              {edit.edited_result?.file_url ? (
                <button type="button" className="task-link-btn" onClick={() => window.open(edit.edited_result?.file_url, "_blank", "noopener,noreferrer")}>
                  查看版本 v{edit.edited_result.version_no}
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function canOpenTask(task: V1TaskListItem): boolean {
  return task.task_type === "main_image" || task.task_type === "detail_page" || task.task_type === "image_edit";
}

function openButtonLabel(taskType: DbTaskType): string {
  if (taskType === "detail_page") {
    return "恢复到详情图页";
  }
  if (taskType === "main_image") {
    return "恢复到主图页";
  }
  return "查看编辑结果";
}

function taskTypeLabel(taskType: DbTaskType): string {
  if (taskType === "main_image") return "主图任务";
  if (taskType === "detail_page") return "详情图任务";
  if (taskType === "image_edit") return "图片编辑";
  return taskType;
}

function statusLabel(status: DbTaskStatus): string {
  const match = STATUS_OPTIONS.find((item) => item.value === status);
  return match?.label ?? status;
}

function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

function formatDate(value: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function normalizeSelection(start: { x: number; y: number }, end: { x: number; y: number }): ImageEditRectangleSelection {
  const x = Math.min(start.x, end.x);
  const y = Math.min(start.y, end.y);
  const width = Math.max(0.001, Math.abs(end.x - start.x));
  const height = Math.max(0.001, Math.abs(end.y - start.y));
  return {
    x: clamp(x, 0, 1),
    y: clamp(y, 0, 1),
    width: clamp(width, 0.001, 1 - x),
    height: clamp(height, 0.001, 1 - y),
    unit: "ratio",
  };
}

function formatSelection(selection: ImageEditRectangleSelection): string {
  return `${Math.round(selection.x * 100)}%, ${Math.round(selection.y * 100)}% · ${Math.round(selection.width * 100)}% x ${Math.round(selection.height * 100)}%`;
}

function modeLabel(mode: string): string {
  if (mode === "full_image_constrained_regeneration") {
    return "全图约束再生成";
  }
  if (mode === "native_inpainting") {
    return "原生局部重绘";
  }
  return mode;
}

function editStatusLabel(status: string): string {
  const mapping: Record<string, string> = {
    pending: "待处理",
    queued: "排队中",
    running: "运行中",
    succeeded: "已完成",
    failed: "失败",
    cancelled: "已取消",
  };
  return mapping[status] ?? status;
}
