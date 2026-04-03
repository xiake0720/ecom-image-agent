import type { TaskRuntimeResult } from "../../types/api";

interface DetailMainResultGalleryProps {
  items: TaskRuntimeResult[];
  selectedFileNames: string[];
  state: "idle" | "loading" | "error" | "empty" | "ready";
  message: string;
  onToggle: (fileName: string) => void;
}

/** 主图结果导入图卡区。 */
export function DetailMainResultGallery({
  items,
  selectedFileNames,
  state,
  message,
  onToggle,
}: DetailMainResultGalleryProps) {
  if (state === "loading") {
    return <div className="detail-empty-state">正在读取主图任务结果...</div>;
  }
  if (state === "error" || state === "empty") {
    return <div className="detail-empty-state">{message}</div>;
  }
  if (!items.length) {
    return <div className="detail-empty-state">选择主图任务后，这里会展示可导入的 completed 结果图卡。</div>;
  }

  return (
    <div className="detail-card-grid detail-card-grid--gallery">
      {items.map((item) => {
        const selected = selectedFileNames.includes(item.file_name);
        return (
          <button
            key={item.id}
            type="button"
            className={`detail-image-card ${selected ? "is-selected" : ""}`}
            onClick={() => onToggle(item.file_name)}
          >
            {item.image_url ? (
              <img src={item.image_url} alt={item.title} className="detail-image-card__media" />
            ) : (
              <div className="detail-image-card__placeholder">无预览</div>
            )}
            <div className="detail-image-card__body">
              <div className="detail-image-card__title-row">
                <strong>{item.title}</strong>
                <span className={`detail-selection-mark ${selected ? "is-selected" : ""}`}>{selected ? "已选中" : "可导入"}</span>
              </div>
              <span>{item.file_name}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
