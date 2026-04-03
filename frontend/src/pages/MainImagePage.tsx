import { useEffect, useMemo, useState, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { submitMainImageTask } from "../services/mainImageApi";
import { fetchTaskRuntime } from "../services/taskApi";
import type { RuntimeResultStatus, TaskRuntimePayload, TaskRuntimeResult, TaskStatus } from "../types/api";
import "./MainImagePage.css";
import { PageShell } from "../components/layout/PageShell";

type UploadLayout = "primary" | "uniform";

interface UploadGallerySectionProps {
  /** 区块标题，用于统一商品图与参考图的上传卡片语义。 */
  title: string;
  /** 区块说明，用于解释当前上传区的用途与限制。 */
  description: string;
  /** 输入框 ID，用于保持 label 与 input 的语义关联。 */
  inputId: string;
  /** 当前已上传文件列表，由页面统一维护。 */
  files: File[];
  /** 文件预览地址列表，与 files 顺序保持一致。 */
  previewUrls: string[];
  /** 上传区布局模式：商品图强调主上传位，参考图使用统一缩略图网格。 */
  layout?: UploadLayout;
  /** 是否允许多选，参考图支持多选追加。 */
  multiple?: boolean;
  /** 最大文件数，仅用于文案与计数提示。 */
  maxFiles?: number;
  /** 添加卡片标题。 */
  addLabel: string;
  /** 添加卡片辅助说明。 */
  addHint: string;
  /** 文件新增回调，由页面层决定是替换还是追加。 */
  onAddFiles: (files: File[]) => void;
  /** 文件删除回调，可选，常用于参考图删除。 */
  onRemoveFile?: (index: number) => void;
}

const LOCAL_STORAGE_TASK_KEY = "main-image-active-task-id";
const POLL_INTERVAL_MS = 3000;
const MAX_REFERENCE_IMAGES = 6;
const MAX_BG_REFERENCE_IMAGES = 4;
const WORKFLOW_STAGES = [
  { key: "ingest_assets", label: "解析商品" },
  { key: "director_v2", label: "风格匹配" },
  { key: "prompt_refine_v2", label: "提示词" },
  { key: "render_images", label: "生成迭代" },
  { key: "run_qc", label: "质检" },
  { key: "finalize", label: "完成" },
] as const;
const PLATFORM_OPTIONS = [
  { label: "天猫", value: "tmall" },
  { label: "京东", value: "jd" },
  { label: "拼多多", value: "pinduoduo" },
  { label: "抖音", value: "douyin" },
] as const;
const CATEGORY_OPTIONS = [{ label: "茶叶", value: "tea" }] as const;
const STYLE_TAGS = ["简洁", "自然", "优雅", "细节", "轻奢", "质感", "暖调", "极简"];
const SHOT_COUNT_OPTIONS = [4, 6, 8, 10];
const IMAGE_SIZE_OPTIONS = ["2K"];

/**
 * 主图生成工作台页面。
 * 职责：保持现有工作台结构不变，把真实提交、队列观测、下载能力和背景参考图上传接到当前页面。
 */
export function MainImagePage() {
  const navigate = useNavigate();
  const [brandName, setBrandName] = useState("");
  const [productName, setProductName] = useState("");
  const [whiteBg, setWhiteBg] = useState<File | null>(null);
  const [referenceImages, setReferenceImages] = useState<File[]>([]);
  const [backgroundReferences, setBackgroundReferences] = useState<File[]>([]);
  const [category, setCategory] = useState("tea");
  const [platform, setPlatform] = useState("tmall");
  const [selectedStyles, setSelectedStyles] = useState<string[]>(["简洁", "自然"]);
  const [shotCount, setShotCount] = useState(8);
  const [ratio, setRatio] = useState("3:4");
  const [imageSize, setImageSize] = useState("2K");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("未提交");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [activeTaskId, setActiveTaskId] = useState(() => window.localStorage.getItem(LOCAL_STORAGE_TASK_KEY) ?? "");
  const [taskRuntime, setTaskRuntime] = useState<TaskRuntimePayload | null>(null);
  const [previewCard, setPreviewCard] = useState<TaskRuntimeResult | null>(null);

  const whiteBgFiles = useMemo(() => (whiteBg ? [whiteBg] : []), [whiteBg]);
  const whiteBgPreviewUrls = useObjectUrls(whiteBgFiles);
  const referencePreviewUrls = useObjectUrls(referenceImages);
  const backgroundReferencePreviewUrls = useObjectUrls(backgroundReferences);
  const styleType = selectedStyles.length > 0 ? selectedStyles.join(" / ") : "高端极简";
  const resultCards = taskRuntime?.results ?? [];
  const activeStageIndex = getActiveStageIndex(taskRuntime?.current_step ?? "", taskRuntime?.status ?? null);
  const progressValue = taskRuntime?.progress_percent ?? 0;
  const progressMessage = taskRuntime?.message ?? "提交任务后将在这里显示真实进度和结果。";
  const runtimeMeta = taskRuntime
    ? [
        taskRuntime.provider_label ? `${taskRuntime.provider_label} / ${taskRuntime.model_label}` : "",
        taskRuntime.status === "running"
          ? "当前任务执行中"
          : taskRuntime.queue_position !== null && taskRuntime.queue_position > 0
            ? `前方 ${taskRuntime.queue_position} 个任务`
            : taskRuntime.queue_size > 0
              ? "已进入执行队列"
              : "",
        taskRuntime.detail_image_count > 0 ? `参考图 ${taskRuntime.detail_image_count}` : "",
        taskRuntime.background_image_count > 0 ? `背景图 ${taskRuntime.background_image_count}` : "",
        taskRuntime.qc_summary.review_required ? `质检警告 ${taskRuntime.qc_summary.warning_count}` : "",
        taskRuntime.qc_summary.failed_count > 0 ? `质检失败 ${taskRuntime.qc_summary.failed_count}` : "",
      ].filter(Boolean)
    : [];

  useEffect(() => {
    if (!previewCard) {
      return undefined;
    }

    const previousOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setPreviewCard(null);
      }
    };

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [previewCard]);

  useEffect(() => {
    if (!activeTaskId) {
      window.localStorage.removeItem(LOCAL_STORAGE_TASK_KEY);
      setTaskRuntime(null);
      setIsPolling(false);
      return undefined;
    }

    window.localStorage.setItem(LOCAL_STORAGE_TASK_KEY, activeTaskId);
    let cancelled = false;
    let timer: number | null = null;

    const loadRuntime = async () => {
      try {
        const runtime = await fetchTaskRuntime(activeTaskId);
        if (cancelled) {
          return;
        }
        setTaskRuntime(runtime);
        setMessage(runtime.message);
        const shouldContinue = !isTerminalTaskStatus(runtime.status);
        setIsPolling(shouldContinue);
        if (shouldContinue) {
          timer = window.setTimeout(loadRuntime, POLL_INTERVAL_MS);
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        const nextMessage = extractErrorMessage(error);
        setMessage(nextMessage);
        setIsPolling(false);
        if (isTaskNotFoundError(error)) {
          window.localStorage.removeItem(LOCAL_STORAGE_TASK_KEY);
          setActiveTaskId("");
          setTaskRuntime(null);
        }
      }
    };

    loadRuntime();

    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [activeTaskId]);

  function toggleStyle(style: string) {
    setSelectedStyles((prev) => {
      if (prev.includes(style)) {
        return prev.filter((item) => item !== style);
      }
      if (prev.length >= 5) {
        return prev;
      }
      return [...prev, style];
    });
  }

  function handleWhiteBgAdd(files: File[]) {
    setWhiteBg(files[0] ?? null);
  }

  function handleReferenceAdd(files: File[]) {
    if (files.length === 0) {
      return;
    }
    setReferenceImages((prev) => [...prev, ...files].slice(0, MAX_REFERENCE_IMAGES));
  }

  function handleReferenceRemove(index: number) {
    setReferenceImages((prev) => prev.filter((_, currentIndex) => currentIndex !== index));
  }

  function handleBackgroundAdd(files: File[]) {
    if (files.length === 0) {
      return;
    }
    setBackgroundReferences((prev) => [...prev, ...files].slice(0, MAX_BG_REFERENCE_IMAGES));
  }

  function handleBackgroundRemove(index: number) {
    setBackgroundReferences((prev) => prev.filter((_, currentIndex) => currentIndex !== index));
  }

  async function submit() {
    if (!whiteBg) {
      setMessage("请先上传商品白底图");
      return;
    }

    setIsSubmitting(true);
    try {
      const summary = await submitMainImageTask({
        whiteBg,
        detailFiles: referenceImages,
        bgFiles: backgroundReferences,
        brandName,
        productName,
        category,
        platform,
        styleType,
        styleNotes: note,
        shotCount,
        aspectRatio: ratio,
        imageSize,
      });
      setPreviewCard(null);
      setTaskRuntime(null);
      setActiveTaskId(summary.task_id);
      setMessage(`任务已提交：${summary.task_id}`);
    } catch (error) {
      setMessage(extractErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  function handlePreview(card: TaskRuntimeResult) {
    if (!card.image_url) {
      return;
    }
    setPreviewCard(card);
  }

  function handleDownload(card: TaskRuntimeResult) {
    if (!card.image_url) {
      return;
    }
    downloadByUrl(card.image_url, card.file_name.split("/").pop() ?? `${card.id}.png`);
  }

  function handleResetActiveTask() {
    setPreviewCard(null);
    setTaskRuntime(null);
    setActiveTaskId("");
    setMessage("已清空当前任务展示，可重新提交新任务。");
  }

  return (
    <PageShell activeKey="main-images">
      <div className="main-workbench">
      <main className="workbench-content">
        <section className="left-panel">
          <UploadGallerySection
            title="上传商品图"
            description="上传白底主商品图，系统会在保持主体结构的前提下生成主图。"
            inputId="white-bg-upload"
            files={whiteBgFiles}
            previewUrls={whiteBgPreviewUrls}
            layout="primary"
            addLabel={whiteBg ? "替换商品图" : "上传商品图"}
            addHint="支持 JPG / PNG / WebP"
            onAddFiles={handleWhiteBgAdd}
            onRemoveFile={whiteBg ? () => setWhiteBg(null) : undefined}
          />

          <UploadGallerySection
            title="上传参考图"
            description="可选，最多上传 6 张产品参考图，用于主体、结构和细节对齐。"
            inputId="reference-upload"
            files={referenceImages}
            previewUrls={referencePreviewUrls}
            layout="uniform"
            multiple
            maxFiles={MAX_REFERENCE_IMAGES}
            addLabel="添加参考图"
            addHint={`最多 ${MAX_REFERENCE_IMAGES} 张`}
            onAddFiles={handleReferenceAdd}
            onRemoveFile={handleReferenceRemove}
          />

          <UploadGallerySection
            title="上传背景参考图"
            description="可选，最多上传 4 张背景风格图，用于氛围、色调和空间语言参考。"
            inputId="background-reference-upload"
            files={backgroundReferences}
            previewUrls={backgroundReferencePreviewUrls}
            layout="uniform"
            multiple
            maxFiles={MAX_BG_REFERENCE_IMAGES}
            addLabel="添加背景图"
            addHint={`最多 ${MAX_BG_REFERENCE_IMAGES} 张`}
            onAddFiles={handleBackgroundAdd}
            onRemoveFile={handleBackgroundRemove}
          />

          <article className="panel-card">
            <h3>选择平台</h3>
            <div className="radio-group">
              {PLATFORM_OPTIONS.map((item) => (
                <label key={item.value} className={`radio-item ${platform === item.value ? "checked" : ""}`}>
                  <input type="radio" name="platform" checked={platform === item.value} onChange={() => setPlatform(item.value)} />
                  {item.label}
                </label>
              ))}
            </div>
          </article>

          <article className="panel-card">
            <h3>选择风格</h3>
            <div className="tag-group">
              {STYLE_TAGS.map((item) => (
                <button
                  key={item}
                  type="button"
                  className={`tag-chip ${selectedStyles.includes(item) ? "selected" : ""}`}
                  onClick={() => toggleStyle(item)}
                >
                  {item}
                </button>
              ))}
            </div>
            <p className="hint">当前会把已选风格合并提交为 `style_type`，背景参考图会单独提交为 `bg_files`。</p>
          </article>

          <article className="panel-card">
            <h3>参数设置</h3>
            <div className="form-grid">
              <label>
                商品类目
                <select value={category} onChange={(event) => setCategory(event.target.value)}>
                  {CATEGORY_OPTIONS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                出图数量
                <select value={String(shotCount)} onChange={(event) => setShotCount(Number(event.target.value))}>
                  {SHOT_COUNT_OPTIONS.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                画面比例
                <select value={ratio} onChange={(event) => setRatio(event.target.value)}>
                  <option>3:4</option>
                  <option>1:1</option>
                  <option>16:9</option>
                </select>
              </label>
              <label>
                图片尺寸
                <select value={imageSize} onChange={(event) => setImageSize(event.target.value)}>
                  {IMAGE_SIZE_OPTIONS.map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
            </div>
          </article>

          <article className="panel-card">
            <h3>文案备注</h3>
            <input
              className="product-name-input"
              type="text"
              placeholder="品牌名称（可选）"
              value={brandName}
              onChange={(event) => setBrandName(event.target.value)}
              maxLength={80}
            />
            <input
              className="product-name-input"
              type="text"
              placeholder="商品名称（可选）"
              value={productName}
              onChange={(event) => setProductName(event.target.value)}
              maxLength={80}
            />
            <textarea
              placeholder="请输入品牌名、核心卖点、风格补充或禁用词；本字段会提交为 style_notes"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              maxLength={200}
            />
            <div className="text-meta">{note.length}/200</div>
            <div className="actions-row">
              <button className="btn-primary" onClick={submit} disabled={isSubmitting}>
                {isSubmitting ? "提交中..." : "开始生成"}
              </button>
              <button className="btn-secondary" type="button" onClick={() => navigate(`/detail-pages${activeTaskId ? `?main_task_id=${activeTaskId}` : ""}`)}>
                生成详情页方案
              </button>
            </div>
            <p className="submit-message">{message}</p>
          </article>
        </section>

        <section className="right-panel">
          <article className="panel-card progress-card">
            <div className="section-head">
              <div>
                <h3>任务进度总览</h3>
                <p className="section-subtitle">{progressMessage}</p>
              </div>
              <span className="section-metric">{progressValue}%</span>
            </div>
            <div className="progress-track" role="progressbar" aria-valuenow={progressValue} aria-valuemin={0} aria-valuemax={100}>
              <div className="progress-fill" style={{ width: `${progressValue}%` }} />
            </div>
            <div className="stage-row">
              {WORKFLOW_STAGES.map((stage, index) => (
                <span key={stage.key} className={index <= activeStageIndex ? "active" : ""}>
                  {stage.label}
                </span>
              ))}
            </div>
            {runtimeMeta.length > 0 ? (
              <div className="runtime-meta-row">
                {runtimeMeta.map((item) => (
                  <span key={item} className="runtime-meta-chip">
                    {item}
                  </span>
                ))}
              </div>
            ) : null}
            {taskRuntime ? (
              <div className="runtime-task-row">
                <span className="runtime-task-id">任务 ID：{taskRuntime.task_id}</span>
                <button type="button" className="runtime-link-btn" onClick={handleResetActiveTask}>
                  清空当前展示
                </button>
              </div>
            ) : null}
          </article>

          <article className="panel-card result-board">
            <div className="section-head">
              <div>
                <h3>结果图区</h3>
                <p className="section-subtitle">右侧结果卡片已全部改为真实任务运行时数据，并增加导出 ZIP 和 QC 摘要。</p>
              </div>
              <div className="board-action-group">
                <span className="section-metric">
                  {taskRuntime ? `${taskRuntime.result_count_completed}/${taskRuntime.result_count_total} 张` : `${resultCards.length} 张`}
                </span>
                {taskRuntime?.export_zip_url ? (
                  <button
                    type="button"
                    className="btn-secondary btn-compact"
                    onClick={() => downloadByUrl(taskRuntime.export_zip_url, `${taskRuntime.task_id}_final_images.zip`)}
                  >
                    下载结果 ZIP
                  </button>
                ) : null}
                {taskRuntime?.full_bundle_zip_url ? (
                  <button
                    type="button"
                    className="btn-secondary btn-compact"
                    onClick={() => downloadByUrl(taskRuntime.full_bundle_zip_url, `${taskRuntime.task_id}_full_bundle.zip`)}
                  >
                    下载任务包
                  </button>
                ) : null}
              </div>
            </div>

            {taskRuntime ? (
              <div className="runtime-summary-row">
                <span className={`runtime-summary-chip ${taskRuntime.qc_summary.passed ? "ok" : "warn"}`}>
                  QC {taskRuntime.qc_summary.passed ? "通过" : "待处理"}
                </span>
                <span className="runtime-summary-chip">警告 {taskRuntime.qc_summary.warning_count}</span>
                <span className="runtime-summary-chip">失败 {taskRuntime.qc_summary.failed_count}</span>
              </div>
            ) : null}

            {resultCards.length === 0 ? (
              <div className="result-empty-state">提交任务后，这里会通过 `GET /api/tasks/{'{task_id}'}/runtime` 展示真实结果。</div>
            ) : (
              <div className="result-grid">
                {resultCards.map((card) => {
                  const canPreview = Boolean(card.image_url);
                  return (
                    <article key={card.id} className="result-card">
                      <button
                        type="button"
                        className="result-image-button"
                        aria-label={`预览 ${card.title} ${card.subtitle}`}
                        disabled={!canPreview}
                        onClick={() => handlePreview(card)}
                      >
                        {canPreview ? (
                          <img src={card.image_url} alt={`${card.title} ${card.subtitle}`} />
                        ) : (
                          <div className={`result-image-placeholder result-image-placeholder-${card.status}`}>
                            <strong>{statusLabel(card.status)}</strong>
                            <span>{card.subtitle || "等待结果"}</span>
                          </div>
                        )}
                      </button>
                      <div className="result-meta">
                        <span className={`status-pill status-${card.status}`}>{statusLabel(card.status)}</span>
                        <div className="result-actions">
                          <button
                            type="button"
                            className="icon-btn"
                            aria-label={`预览 ${card.title}`}
                            disabled={!canPreview}
                            onClick={() => handlePreview(card)}
                          >
                            <EyeIcon />
                          </button>
                          <button
                            type="button"
                            className="icon-btn"
                            aria-label={`下载 ${card.title}`}
                            disabled={!canPreview}
                            onClick={() => handleDownload(card)}
                          >
                            <DownloadIcon />
                          </button>
                          <button type="button" className="icon-btn" aria-label={`重试 ${card.title}`} disabled>
                            <RefreshIcon />
                          </button>
                        </div>
                      </div>
                      <p className="result-title">{card.title} · {card.subtitle}</p>
                      <p className="result-caption">{buildResultMeta(card)}</p>
                    </article>
                  );
                })}
              </div>
            )}
          </article>
        </section>
      </main>

      <ImagePreviewDialog card={previewCard} onClose={() => setPreviewCard(null)} />
      </div>
    </PageShell>
  );
}

/**
 * 统一上传区组件。
 * 职责：复用同一套卡片语言，商品图突出主上传位，参考图强调规整网格与删除操作。
 */
function UploadGallerySection({
  title,
  description,
  inputId,
  files,
  previewUrls,
  layout = "uniform",
  multiple = false,
  maxFiles,
  addLabel,
  addHint,
  onAddFiles,
  onRemoveFile,
}: UploadGallerySectionProps) {
  const isPrimary = layout === "primary";
  const hasFiles = previewUrls.length > 0;
  const canAddMore = maxFiles === undefined || files.length < maxFiles;
  const showAddTile = canAddMore && (!isPrimary || hasFiles);

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFiles = Array.from(event.target.files ?? []);
    onAddFiles(multiple ? nextFiles : nextFiles.slice(0, 1));
    event.target.value = "";
  }

  return (
    <article className="panel-card upload-section-card">
      <div className="section-head upload-section-head">
        <div>
          <h3>{title}</h3>
          <p className="upload-description">{description}</p>
        </div>
        <span className="section-metric">
          已选 {files.length}{maxFiles ? ` / ${maxFiles}` : ""}
        </span>
      </div>

      <div className={`upload-gallery-grid ${isPrimary ? "upload-gallery-grid-primary" : "upload-gallery-grid-uniform"}`}>
        {hasFiles ? (
          previewUrls.map((previewUrl, index) => (
            <div className={`upload-tile upload-thumb ${isPrimary ? "upload-tile-primary" : ""}`} key={`${inputId}-${index}`}>
              {onRemoveFile ? (
                <button
                  type="button"
                  className="thumb-delete-btn"
                  aria-label={`删除${title}${index + 1}`}
                  onClick={() => onRemoveFile(index)}
                >
                  <CloseIcon />
                </button>
              ) : null}
              <img src={previewUrl} alt={`${title} ${index + 1}`} />
              <div className="upload-thumb-meta">
                <strong>{isPrimary ? "主商品图" : `${title} ${index + 1}`}</strong>
                <span>{files[index]?.name ?? `已上传文件 ${index + 1}`}</span>
              </div>
            </div>
          ))
        ) : (
          <label className={`upload-tile upload-empty ${isPrimary ? "upload-empty-primary" : ""}`} htmlFor={inputId}>
            <span className="upload-add-icon">+</span>
            <strong>{isPrimary ? "先上传商品图" : addLabel}</strong>
            <span>{isPrimary ? "主上传位会优先展示在这里" : "上传后会按统一缩略图网格展示"}</span>
          </label>
        )}

        {showAddTile ? (
          <label className={`upload-tile upload-add ${isPrimary ? "upload-add-secondary" : ""}`} htmlFor={inputId}>
            <span className="upload-add-icon">+</span>
            <strong>{addLabel}</strong>
            <small>{addHint}</small>
          </label>
        ) : null}
      </div>

      <input id={inputId} type="file" accept="image/*" hidden multiple={multiple} onChange={handleInputChange} />
      <p className="hint">{multiple ? "缩略图支持右上角删除，删除后网格会自动补位。" : "商品图支持重新上传替换，保留主上传位结构。"}</p>
    </article>
  );
}

/**
 * 结果图预览弹层。
 * 职责：在当前页内预览 runtime 返回的真实结果图，不引入额外路由。
 */
function ImagePreviewDialog({ card, onClose }: { card: TaskRuntimeResult | null; onClose: () => void }) {
  if (!card) {
    return null;
  }

  return (
    <div className="image-preview-overlay" role="presentation" onClick={onClose}>
      <div
        className="image-preview-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={`${card.title} 大图预览`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="image-preview-header">
          <div>
            <h3>{card.title}</h3>
            <p>{card.subtitle}</p>
          </div>
          <button type="button" className="preview-close-btn" aria-label="关闭预览" onClick={onClose}>
            <CloseIcon />
          </button>
        </div>
        <div className="image-preview-stage">
          <img src={card.image_url} alt={`${card.title} ${card.subtitle}`} />
        </div>
      </div>
    </div>
  );
}

/**
 * 文件预览 URL 派生钩子。
 * 职责：统一创建并释放 object URL，避免上传区反复生成预览地址导致内存泄漏。
 */
function useObjectUrls(files: File[]) {
  const [urls, setUrls] = useState<string[]>([]);

  useEffect(() => {
    const nextUrls = files.map((file) => URL.createObjectURL(file));
    setUrls(nextUrls);

    return () => {
      nextUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [files]);

  return urls;
}

function getActiveStageIndex(currentStep: string, taskStatus: TaskStatus | null): number {
  if (taskStatus === "completed" || taskStatus === "review_required") {
    return WORKFLOW_STAGES.length - 1;
  }
  if (!currentStep || currentStep === "queued") {
    return -1;
  }
  return WORKFLOW_STAGES.findIndex((stage) => stage.key === currentStep);
}

function isTerminalTaskStatus(status: TaskStatus): boolean {
  return status === "completed" || status === "review_required" || status === "failed";
}

function taskStatusLabel(status: TaskStatus | null, isPollingRuntime: boolean): string {
  if (!status) {
    return "待提交";
  }
  if (status === "created") {
    return isPollingRuntime ? "排队中" : "已提交";
  }
  if (status === "running") {
    return "生成中";
  }
  if (status === "completed") {
    return "已完成";
  }
  if (status === "review_required") {
    return "待复核";
  }
  return "已失败";
}

function statusLabel(status: RuntimeResultStatus): string {
  if (status === "completed") return "完成";
  if (status === "queued") return "队列中";
  if (status === "running") return "生成中";
  return "失败";
}

function buildResultMeta(card: TaskRuntimeResult): string {
  if (!card.generated_at) {
    return card.status === "completed" ? "已生成" : "等待生成";
  }
  const time = new Date(card.generated_at);
  const timeLabel = Number.isNaN(time.getTime()) ? card.generated_at : time.toLocaleString();
  const sizeLabel = card.width && card.height ? `${card.width}×${card.height}` : "尺寸待定";
  return `${sizeLabel} · ${timeLabel}`;
}

function extractErrorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null) {
    const maybeError = error as { response?: { data?: { message?: string } }; message?: string };
    return maybeError.response?.data?.message || maybeError.message || "请求失败，请稍后重试";
  }
  return "请求失败，请稍后重试";
}

function isTaskNotFoundError(error: unknown): boolean {
  if (typeof error !== "object" || error === null) {
    return false;
  }
  const maybeError = error as { response?: { data?: { code?: number } } };
  return maybeError.response?.data?.code === 4044;
}

function downloadByUrl(url: string, filename: string) {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3v11m0 0 4-4m-4 4-4-4M4 17v3h16v-3" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 11a8 8 0 1 0 2 5m0 0v-5h-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M15 18H9m10-2H5l2-2v-3a5 5 0 1 1 10 0v3l2 2Z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function GearIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m12 3 1.4 1.8 2.2.4.6 2.2 1.8 1.4-1 2 1 2-1.8 1.4-.6 2.2-2.2.4L12 21l-1.4-1.8-2.2-.4-.6-2.2L6 15.2l1-2-1-2 1.8-1.4.6-2.2 2.2-.4L12 3Zm0 6.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5Z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 7 17 17M17 7 7 17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
