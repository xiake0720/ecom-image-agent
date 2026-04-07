import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { DetailAssetUploader } from "../components/detail/DetailAssetUploader";
import { DetailCopyPreview } from "../components/detail/DetailCopyPreview";
import { DetailGoalForm } from "../components/detail/DetailGoalForm";
import { DetailMainResultGallery } from "../components/detail/DetailMainResultGallery";
import { DetailPlanPreview } from "../components/detail/DetailPlanPreview";
import { DetailProductForm } from "../components/detail/DetailProductForm";
import { DetailPromptPreview } from "../components/detail/DetailPromptPreview";
import { DetailResultGallery } from "../components/detail/DetailResultGallery";
import { DetailRuntimeSidebar } from "../components/detail/DetailRuntimeSidebar";
import { DetailTaskSourcePicker } from "../components/detail/DetailTaskSourcePicker";
import { PageHeader } from "../components/common/PageHeader";
import { SectionCard } from "../components/common/SectionCard";
import { PageShell } from "../components/layout/PageShell";
import { fetchDetailRuntime, submitDetailJob } from "../services/detailPageApi";
import { fetchTaskRuntime, fetchTasks } from "../services/taskApi";
import type { TaskRuntimeResult, TaskSummary } from "../types/api";
import type { DetailPageRuntimeImage, DetailPageRuntimePayload } from "../types/detail";
import "./DetailPageGeneratorPage.css";

const POLL_INTERVAL_MS = 3000;

type AssetRole = "packaging" | "dry_leaf" | "tea_soup" | "leaf_bottom" | "scene_ref" | "bg_ref";
type FileBucket = Record<AssetRole, File[]>;

type SpecForm = {
  net_content: string;
  origin: string;
  ingredients: string;
  shelf_life: string;
  storage: string;
};

const emptySpec: SpecForm = { net_content: "", origin: "", ingredients: "", shelf_life: "", storage: "" };
const emptyBuckets: FileBucket = {
  packaging: [],
  dry_leaf: [],
  tea_soup: [],
  leaf_bottom: [],
  scene_ref: [],
  bg_ref: [],
};

/** 从 axios / 普通异常中提取可展示的错误文案。 */
function extractApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const payload = error.response?.data as { message?: string; code?: number | string; requestId?: string } | undefined;
    const message = payload?.message || error.message || "请求失败";
    const code = payload?.code ? ` (code: ${payload.code})` : "";
    const requestId = payload?.requestId ? ` [requestId: ${payload.requestId}]` : "";
    return `${message}${code}${requestId}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "未知错误，请查看后端日志。";
}

/** 茶叶详情图正式工作台页面。 */
export function DetailPageGeneratorPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [brandName, setBrandName] = useState("");
  const [productName, setProductName] = useState("");
  const [teaType, setTeaType] = useState("乌龙茶");
  const [platform, setPlatform] = useState("tmall");
  const [stylePreset, setStylePreset] = useState("tea_tmall_premium_light");
  const [priceBand, setPriceBand] = useState("");
  const [targetSliceCount, setTargetSliceCount] = useState(8);
  const [styleNotes, setStyleNotes] = useState("");
  const [extraRequirements, setExtraRequirements] = useState("");
  const [brewSuggestion, setBrewSuggestion] = useState("");
  const [sellingPointsInput, setSellingPointsInput] = useState("茶香层次丰富\n回甘持久\n适合送礼");
  const [preferMainResultFirst, setPreferMainResultFirst] = useState(true);
  const [specForm, setSpecForm] = useState<SpecForm>(emptySpec);
  const [fileBuckets, setFileBuckets] = useState<FileBucket>(emptyBuckets);

  const [mainTaskId, setMainTaskId] = useState(searchParams.get("main_task_id") ?? "");
  const [selectedMainResults, setSelectedMainResults] = useState<string[]>([]);
  const [mainTaskOptions, setMainTaskOptions] = useState<TaskSummary[]>([]);
  const [mainTaskResults, setMainTaskResults] = useState<TaskRuntimeResult[]>([]);
  const [mainSourceState, setMainSourceState] = useState<"idle" | "loading" | "error" | "empty" | "ready">("idle");
  const [mainSourceMessage, setMainSourceMessage] = useState("选择主图任务后，可导入 completed 结果作为详情图参考。");

  const [detailTaskId, setDetailTaskId] = useState("");
  const [runtime, setRuntime] = useState<DetailPageRuntimePayload | null>(null);
  const [message, setMessage] = useState("先配置素材与商品信息，再生成规划或完整详情图。");
  const [pageError, setPageError] = useState("");
  const [previewImage, setPreviewImage] = useState<DetailPageRuntimeImage | null>(null);
  const [submitting, setSubmitting] = useState<"plan" | "full" | "">("");

  useEffect(() => {
    fetchTasks()
      .then((rows) => {
        setMainTaskOptions(rows.filter((item) => item.task_type === "main_image").slice(0, 12));
      })
      .catch((error) => {
        setPageError(`主图任务列表加载失败：${extractApiErrorMessage(error)}`);
      });
  }, []);

  useEffect(() => {
    if (!mainTaskId) {
      setMainTaskResults([]);
      setSelectedMainResults([]);
      setMainSourceState("idle");
      setMainSourceMessage("当前未绑定主图任务。");
      return;
    }
    setMainSourceState("loading");
    setMainSourceMessage("正在读取主图任务结果...");
    fetchTaskRuntime(mainTaskId)
      .then((payload) => {
        const completed = payload.results.filter((item) => item.status === "completed");
        setMainTaskResults(completed);
        if (!completed.length) {
          setSelectedMainResults([]);
          setMainSourceState("empty");
          setMainSourceMessage("该主图任务暂无 completed 结果。");
          return;
        }
        setMainSourceState("ready");
        setSelectedMainResults((prev) => {
          const valid = prev.filter((name) => completed.some((item) => item.file_name === name));
          return valid.length > 0 ? valid : [completed[0].file_name];
        });
        setMainSourceMessage(`已导入 ${completed.length} 张主图结果，可多选。`);
      })
      .catch((error) => {
        setMainTaskResults([]);
        setSelectedMainResults([]);
        setMainSourceState("error");
        setMainSourceMessage(`主图结果加载失败：${extractApiErrorMessage(error)}`);
      });
  }, [mainTaskId]);

  useEffect(() => {
    if (!detailTaskId) {
      return;
    }
    let timer: number | null = null;
    let cancelled = false;
    const poll = async () => {
      try {
        const data = await fetchDetailRuntime(detailTaskId);
        if (cancelled) {
          return;
        }
        setRuntime(data);
        setMessage(data.message || "详情图任务运行中");
        if (data.error_message) {
          setPageError(data.error_message);
        }
        if (!isTerminalDetailStatus(data.status)) {
          timer = window.setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch (error) {
        if (!cancelled) {
          const parsedError = extractApiErrorMessage(error);
          setMessage("详情图运行时获取失败");
          setPageError(parsedError);
        }
      }
    };
    poll();
    return () => {
      cancelled = true;
      if (timer !== null) {
        window.clearTimeout(timer);
      }
    };
  }, [detailTaskId]);

  const parsedSellingPoints = useMemo(
    () =>
      sellingPointsInput
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean),
    [sellingPointsInput]
  );

  function appendFiles(role: AssetRole, files: File[]) {
    if (!files.length) return;
    setFileBuckets((prev) => ({ ...prev, [role]: [...prev[role], ...files] }));
  }

  function removeFile(role: AssetRole, index: number) {
    setFileBuckets((prev) => ({ ...prev, [role]: prev[role].filter((_, itemIndex) => itemIndex !== index) }));
  }

  function toggleMainResult(fileName: string) {
    setSelectedMainResults((prev) => {
      if (prev.includes(fileName)) {
        const next = prev.filter((item) => item !== fileName);
        return next.length > 0 ? next : [fileName];
      }
      return [...prev, fileName];
    });
  }

  function importRecentMainTask() {
    if (!mainTaskOptions.length) {
      setMainSourceState("error");
      setMainSourceMessage("暂无可导入的主图任务。");
      return;
    }
    setMainTaskId(mainTaskOptions[0].task_id);
  }

  async function submit(mode: "plan" | "full") {
    setSubmitting(mode);
    setPageError("");
    setMessage(mode === "plan" ? "正在生成规划、文案与 Prompt..." : "任务已创建，正在启动详情图生成...");
    try {
      const result = await submitDetailJob({
        mode,
        brandName,
        productName,
        teaType,
        platform,
        stylePreset,
        priceBand,
        targetSliceCount,
        imageSize: "2K",
        mainImageTaskId: mainTaskId,
        selectedMainResultIds: selectedMainResults,
        sellingPoints: parsedSellingPoints,
        specs: specForm,
        styleNotes,
        brewSuggestion,
        extraRequirements,
        preferMainResultFirst,
        packagingFiles: fileBuckets.packaging,
        dryLeafFiles: fileBuckets.dry_leaf,
        teaSoupFiles: fileBuckets.tea_soup,
        leafBottomFiles: fileBuckets.leaf_bottom,
        sceneRefFiles: fileBuckets.scene_ref,
        bgRefFiles: fileBuckets.bg_ref,
      });
      setDetailTaskId(result.task_id);
      const runtimePayload = await fetchDetailRuntime(result.task_id);
      setRuntime(runtimePayload);
      setMessage(runtimePayload.message || (mode === "plan" ? "规划已生成。" : "详情图任务已提交。"));
      if (runtimePayload.error_message) {
        setPageError(runtimePayload.error_message);
      }
    } catch (error) {
      const parsedError = extractApiErrorMessage(error);
      setPageError(parsedError);
      setMessage(`提交失败：${parsedError}`);
    } finally {
      setSubmitting("");
    }
  }

  function resetForm() {
    setBrandName("");
    setProductName("");
    setTeaType("乌龙茶");
    setPlatform("tmall");
    setStylePreset("tea_tmall_premium_light");
    setPriceBand("");
    setTargetSliceCount(8);
    setStyleNotes("");
    setExtraRequirements("");
    setBrewSuggestion("");
    setSellingPointsInput("");
    setPreferMainResultFirst(true);
    setSpecForm(emptySpec);
    setFileBuckets(emptyBuckets);
    setSelectedMainResults([]);
    setRuntime(null);
    setDetailTaskId("");
    setMessage("已清空当前任务。");
    setPageError("");
  }

  function handleDownloadImage(image: DetailPageRuntimeImage) {
    if (!image.image_url) {
      return;
    }
    const link = document.createElement("a");
    link.href = image.image_url;
    link.download = image.file_name.split("/").pop() || `${image.page_id}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  return (
    <PageShell activeKey="detail-pages">
      <PageHeader
        title="茶叶详情图工作台"
        subtitle="导演 Agent 负责规划、文案与 Prompt，生产 Graph 负责执行、QC、导出与 runtime 轮询。"
        actions={
          <div className="header-actions detail-page-header-actions">
            <button type="button" className="btn-secondary" disabled={submitting !== ""} onClick={() => submit("plan")}>
              {submitting === "plan" ? "规划中..." : "生成规划"}
            </button>
            <button type="button" className="btn-primary" disabled={submitting !== ""} onClick={() => submit("full")}>
              {submitting === "full" ? "生成中..." : "开始完整生成"}
            </button>
          </div>
        }
      />

      <div className="detail-workbench">
        <aside className="detail-column detail-column--left">
          <SectionCard title="主图来源">
            <DetailTaskSourcePicker
              mainTaskId={mainTaskId}
              mainTaskOptions={mainTaskOptions}
              sourceState={mainSourceState}
              sourceMessage={mainSourceMessage}
              importedCount={selectedMainResults.length}
              onChangeTaskId={setMainTaskId}
              onImportRecent={importRecentMainTask}
            />
          </SectionCard>

          <SectionCard title="详情图素材">
            <div className="detail-stack">
              <DetailAssetUploader
                roleKey="packaging"
                label="包装图"
                description="优先保留真实包装结构与品牌识别。"
                files={fileBuckets.packaging}
                onAdd={(files) => appendFiles("packaging", files)}
                onRemove={(index) => removeFile("packaging", index)}
              />
              <DetailAssetUploader
                roleKey="dry_leaf"
                label="茶干图"
                description="用于干茶条索、色泽与原叶细节页。"
                files={fileBuckets.dry_leaf}
                onAdd={(files) => appendFiles("dry_leaf", files)}
                onRemove={(index) => removeFile("dry_leaf", index)}
              />
              <DetailAssetUploader
                roleKey="tea_soup"
                label="茶汤图"
                description="用于茶汤色泽、通透感和饮用氛围页。"
                files={fileBuckets.tea_soup}
                onAdd={(files) => appendFiles("tea_soup", files)}
                onRemove={(index) => removeFile("tea_soup", index)}
              />
              <DetailAssetUploader
                roleKey="leaf_bottom"
                label="叶底图"
                description="用于叶底舒展和原料真实度页。"
                files={fileBuckets.leaf_bottom}
                onAdd={(files) => appendFiles("leaf_bottom", files)}
                onRemove={(index) => removeFile("leaf_bottom", index)}
              />
              <DetailAssetUploader
                roleKey="scene_ref"
                label="场景参考图"
                description="只学习空间氛围与镜头语言，不替换产品主体。"
                files={fileBuckets.scene_ref}
                onAdd={(files) => appendFiles("scene_ref", files)}
                onRemove={(index) => removeFile("scene_ref", index)}
              />
              <DetailAssetUploader
                roleKey="bg_ref"
                label="背景参考图"
                description="只学习背景气质与色调，不改包装与品牌文字。"
                files={fileBuckets.bg_ref}
                onAdd={(files) => appendFiles("bg_ref", files)}
                onRemove={(index) => removeFile("bg_ref", index)}
              />
            </div>
          </SectionCard>

          <SectionCard title="商品信息">
            <DetailProductForm
              brandName={brandName}
              productName={productName}
              teaType={teaType}
              platform={platform}
              stylePreset={stylePreset}
              priceBand={priceBand}
              brewSuggestion={brewSuggestion}
              specs={specForm}
              onBrandNameChange={setBrandName}
              onProductNameChange={setProductName}
              onTeaTypeChange={setTeaType}
              onPlatformChange={setPlatform}
              onStylePresetChange={setStylePreset}
              onPriceBandChange={setPriceBand}
              onBrewSuggestionChange={setBrewSuggestion}
              onSpecChange={(key, value) => setSpecForm((prev) => ({ ...prev, [key]: value }))}
            />
          </SectionCard>

          <SectionCard title="目标与补充">
            <DetailGoalForm
              targetSliceCount={targetSliceCount}
              sellingPointsInput={sellingPointsInput}
              styleNotes={styleNotes}
              extraRequirements={extraRequirements}
              preferMainResultFirst={preferMainResultFirst}
              onTargetSliceCountChange={setTargetSliceCount}
              onSellingPointsChange={setSellingPointsInput}
              onStyleNotesChange={setStyleNotes}
              onExtraRequirementsChange={setExtraRequirements}
              onPreferMainResultFirstChange={setPreferMainResultFirst}
              onReset={resetForm}
              onBackToMain={() => navigate("/main-images")}
            />
          </SectionCard>
        </aside>

        <main className="detail-column detail-column--main">
          {pageError || runtime?.error_message ? (
            <div className="detail-page-banner detail-page-banner--error">{pageError || runtime?.error_message}</div>
          ) : null}

          <SectionCard title="主图导入预览">
            <DetailMainResultGallery
              items={mainTaskResults}
              selectedFileNames={selectedMainResults}
              state={mainSourceState}
              message={mainSourceMessage}
              onToggle={toggleMainResult}
            />
          </SectionCard>

          <SectionCard title="规划预览">
            <DetailPlanPreview
              plan={runtime?.plan ?? null}
              promptPlan={runtime?.prompt_plan ?? []}
              message="先生成规划后，这里会展示每张 3:4 单屏图的主题、目标和引用关系。"
            />
          </SectionCard>

          <SectionCard title="文案预览">
            <DetailCopyPreview plan={runtime?.plan ?? null} copyBlocks={runtime?.copy_blocks ?? []} />
          </SectionCard>

          <SectionCard title="Prompt 摘要">
            <DetailPromptPreview promptPlan={runtime?.prompt_plan ?? []} />
          </SectionCard>

          <SectionCard title="结果图区">
            <DetailResultGallery
              images={runtime?.images ?? []}
              onPreview={setPreviewImage}
              onDownload={handleDownloadImage}
            />
          </SectionCard>
        </main>

        <aside className="detail-column detail-column--right">
          <SectionCard title="运行时侧栏">
            <DetailRuntimeSidebar runtime={runtime} fallbackTaskId={detailTaskId} message={message} pageError={pageError} />
          </SectionCard>
        </aside>
      </div>

      {previewImage ? (
        <div className="detail-preview-modal" role="presentation" onClick={() => setPreviewImage(null)}>
          <div className="detail-preview-modal__dialog" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="detail-preview-modal__header">
              <div>
                <strong>{previewImage.title}</strong>
                <p>{previewImage.reference_roles.join(" / ") || "无参考图说明"}</p>
              </div>
              <button type="button" className="detail-preview-modal__close" onClick={() => setPreviewImage(null)}>
                关闭
              </button>
            </div>
            {previewImage.image_url ? <img src={previewImage.image_url} alt={previewImage.title} className="detail-preview-modal__image" /> : null}
          </div>
        </div>
      ) : null}
    </PageShell>
  );
}

function isTerminalDetailStatus(status: DetailPageRuntimePayload["status"]) {
  return status === "completed" || status === "review_required" || status === "failed";
}
