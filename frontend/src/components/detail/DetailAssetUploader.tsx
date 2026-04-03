import { useEffect, useState } from "react";

interface DetailAssetUploaderProps {
  roleKey: string;
  label: string;
  description: string;
  files: File[];
  onAdd: (files: File[]) => void;
  onRemove: (index: number) => void;
}

/** 详情图素材上传器。 */
export function DetailAssetUploader({ roleKey, label, description, files, onAdd, onRemove }: DetailAssetUploaderProps) {
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);

  useEffect(() => {
    const urls = files.map((file) => URL.createObjectURL(file));
    setPreviewUrls(urls);
    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [files]);

  return (
    <div className="detail-uploader">
      <div className="detail-uploader__header">
        <div>
          <strong>{label}</strong>
          <p>{description}</p>
        </div>
        <span className="detail-badge detail-badge--neutral">{files.length} 张</span>
      </div>

      <div className="detail-upload-grid">
        {previewUrls.map((url, index) => (
          <div key={`${files[index]?.name ?? roleKey}-${index}`} className="detail-upload-tile detail-upload-tile--preview">
            <button type="button" className="detail-upload-remove" onClick={() => onRemove(index)} aria-label={`删除 ${label} ${index + 1}`}>
              ×
            </button>
            <img src={url} alt={`${label} ${index + 1}`} />
            <span>{files[index]?.name ?? `${label} ${index + 1}`}</span>
          </div>
        ))}

        <label htmlFor={`detail-upload-${roleKey}`} className="detail-upload-tile detail-upload-tile--add">
          <span>+</span>
          <strong>上传 {label}</strong>
          <small>支持多选</small>
        </label>
      </div>

      <input
        id={`detail-upload-${roleKey}`}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(event) => {
          onAdd(Array.from(event.target.files ?? []));
          event.target.value = "";
        }}
      />
    </div>
  );
}
