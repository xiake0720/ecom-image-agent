import type { DetailPageRuntimePayload } from "../../types/detail";

interface DetailRuntimeSidebarProps {
  runtime: DetailPageRuntimePayload | null;
  fallbackTaskId: string;
  message: string;
  pageError: string;
}

/** 详情图右侧运行时侧栏。 */
export function DetailRuntimeSidebar({ runtime, fallbackTaskId, message, pageError }: DetailRuntimeSidebarProps) {
  const progressPercent = runtime?.progress_percent ?? 0;
  const qc = runtime?.qc_summary;

  return (
    <div className="detail-runtime-sidebar">
      <div className="detail-runtime-panel">
        <div className="detail-runtime-panel__header">
          <strong>任务状态</strong>
          <span className={`detail-badge detail-badge--${runtime?.status ?? "idle"}`}>{statusLabel(runtime?.status)}</span>
        </div>
        <div className="detail-progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progressPercent}>
          <div className="detail-progress-fill" style={{ width: `${progressPercent}%` }} />
        </div>
        <div className="detail-meta-list">
          <div><span>任务 ID</span><strong>{runtime?.task_id || fallbackTaskId || "-"}</strong></div>
          <div><span>当前阶段</span><strong>{runtime?.current_stage_label || "未开始"}</strong></div>
          <div><span>已生成 / 计划</span><strong>{runtime?.generated_count ?? 0} / {runtime?.planned_count ?? 0}</strong></div>
          <div><span>QC</span><strong>{qc ? `${qc.warning_count} 警告 / ${qc.failed_count} 失败` : "待执行"}</strong></div>
        </div>
      </div>

      <div className="detail-runtime-panel">
        <div className="detail-runtime-panel__header">
          <strong>提示与错误</strong>
          <span className={`detail-badge detail-badge--${pageError || runtime?.error_message ? "failed" : "neutral"}`}>
            {pageError || runtime?.error_message ? "需处理" : "正常"}
          </span>
        </div>
        <p className="detail-runtime-message">{runtime?.message || message}</p>
        {pageError ? <p className="detail-error-text">{pageError}</p> : null}
        {runtime?.error_message ? <p className="detail-error-text">{runtime.error_message}</p> : null}
      </div>

      <div className="detail-runtime-panel">
        <div className="detail-runtime-panel__header">
          <strong>QC 摘要</strong>
          <span className={`detail-badge detail-badge--${qc?.passed ? "completed" : "warning"}`}>{qc?.passed ? "通过" : "待复核"}</span>
        </div>
        {qc?.issues.length ? (
          <ul className="detail-list">
            {qc.issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        ) : (
          <div className="detail-empty-state detail-empty-state--compact">暂无 QC 问题。</div>
        )}
        {runtime?.export_zip_url ? (
          <a className="btn-primary detail-runtime-download" href={runtime.export_zip_url} download>
            下载 ZIP
          </a>
        ) : null}
      </div>
    </div>
  );
}

function statusLabel(status: DetailPageRuntimePayload["status"] | undefined): string {
  if (status === "running") return "运行中";
  if (status === "completed") return "已完成";
  if (status === "review_required") return "待复核";
  if (status === "failed") return "失败";
  if (status === "created") return "已提交";
  return "待开始";
}
