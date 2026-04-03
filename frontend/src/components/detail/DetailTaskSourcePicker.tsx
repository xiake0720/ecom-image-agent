import type { TaskSummary } from "../../types/api";

interface DetailTaskSourcePickerProps {
  mainTaskId: string;
  mainTaskOptions: TaskSummary[];
  sourceState: "idle" | "loading" | "error" | "empty" | "ready";
  sourceMessage: string;
  importedCount: number;
  onChangeTaskId: (taskId: string) => void;
  onImportRecent: () => void;
}

/** 主图任务来源选择器。 */
export function DetailTaskSourcePicker({
  mainTaskId,
  mainTaskOptions,
  sourceState,
  sourceMessage,
  importedCount,
  onChangeTaskId,
  onImportRecent,
}: DetailTaskSourcePickerProps) {
  return (
    <div className="detail-stack">
      <div className="detail-field">
        <label htmlFor="detail-main-task-select">主图任务来源</label>
        <select
          id="detail-main-task-select"
          className="detail-input"
          value={mainTaskId}
          onChange={(event) => onChangeTaskId(event.target.value)}
        >
          <option value="">不导入主图结果</option>
          {mainTaskOptions.map((item) => (
            <option key={item.task_id} value={item.task_id}>
              {item.title || item.task_id}
            </option>
          ))}
        </select>
      </div>

      <div className="detail-inline-actions">
        <button type="button" className="btn-secondary" onClick={onImportRecent}>
          导入最近主图任务
        </button>
        <span className={`detail-badge detail-badge--${sourceState}`}>已导入 {importedCount} 张</span>
      </div>

      <p className="detail-helper">{sourceMessage}</p>
    </div>
  );
}
