import type { DetailPageRuntimeImage } from "../../types/detail";

interface DetailResultGalleryProps {
  images: DetailPageRuntimeImage[];
  onPreview: (image: DetailPageRuntimeImage) => void;
  onDownload: (image: DetailPageRuntimeImage) => void;
}

/** 结果图画廊。 */
export function DetailResultGallery({ images, onPreview, onDownload }: DetailResultGalleryProps) {
  if (!images.length) {
    return <div className="detail-empty-state">完整生成后，这里会展示详情图结果、下载入口和单页状态。</div>;
  }

  return (
    <div className="detail-card-grid detail-card-grid--result">
      {images.map((image) => {
        const canPreview = Boolean(image.image_url);
        return (
          <article key={image.image_id} className={`detail-result-card detail-result-card--${image.status}`}>
            <button
              type="button"
              className="detail-result-card__media-button"
              disabled={!canPreview}
              onClick={() => canPreview && onPreview(image)}
            >
              {canPreview ? (
                <img src={image.image_url} alt={image.title} className="detail-result-card__media" />
              ) : (
                <div className="detail-result-card__placeholder">{statusLabel(image.status)}</div>
              )}
            </button>
            <div className="detail-result-card__body">
              <div className="detail-result-card__title-row">
                <strong>{image.title}</strong>
                <span className={`detail-badge detail-badge--${image.status}`}>{statusLabel(image.status)}</span>
              </div>
              <p>{image.reference_roles.join(" / ") || "等待绑定"}</p>
              <p>{image.width && image.height ? `${image.width} × ${image.height}` : "尺寸待返回"}</p>
              {image.error_message ? <p className="detail-error-text">{image.error_message}</p> : null}
            </div>
            <div className="detail-inline-actions">
              <button type="button" className="btn-secondary btn-compact" onClick={() => canPreview && onPreview(image)} disabled={!canPreview}>
                预览
              </button>
              <button type="button" className="btn-secondary btn-compact" onClick={() => canPreview && onDownload(image)} disabled={!canPreview}>
                下载单张
              </button>
              <button type="button" className="btn-secondary btn-compact" disabled>
                单页重试
              </button>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function statusLabel(status: DetailPageRuntimeImage["status"]): string {
  if (status === "completed") return "已完成";
  if (status === "running") return "生成中";
  if (status === "failed") return "失败";
  return "队列中";
}
