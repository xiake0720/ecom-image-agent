import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { PageHeader } from "../components/common/PageHeader";
import { SectionCard } from "../components/common/SectionCard";
import { PageShell } from "../components/layout/PageShell";
import { fetchDetailRuntime, submitDetailJob } from "../services/detailPageApi";
import { fetchTaskRuntime, fetchTasks } from "../services/taskApi";
import type { TaskRuntimeResult, TaskSummary } from "../types/api";
import type { DetailPageRuntimeImage, DetailPageRuntimePayload } from "../types/detail";

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

/** 详情图真实任务页。 */
export function DetailPageGeneratorPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [brandName, setBrandName] = useState("");
  const [productName, setProductName] = useState("");
  const [teaType, setTeaType] = useState("乌龙茶");
  const [platform, setPlatform] = useState("tmall");
  const [stylePreset, setStylePreset] = useState("tea_tmall_premium_light");
  const [priceBand, setPriceBand] = useState("");
  const [targetSliceCount, setTargetSliceCount] = useState(4);
  const [styleNotes, setStyleNotes] = useState("");
  const [extraRequirements, setExtraRequirements] = useState("");
  const [brewSuggestion, setBrewSuggestion] = useState("");
  const [sellingPointsInput, setSellingPointsInput] = useState("茶香层次丰富\n回甘持久\n适合送礼");
  const [preferMainResultFirst, setPreferMainResultFirst] = useState(true);
  const [specForm, setSpecForm] = useState<SpecForm>(emptySpec);
  const [fileBuckets, setFileBuckets] = useState<FileBucket>({ packaging: [], dry_leaf: [], tea_soup: [], leaf_bottom: [], scene_ref: [], bg_ref: [] });
  const [mainTaskId, setMainTaskId] = useState(searchParams.get("main_task_id") ?? "");
  const [selectedMainResults, setSelectedMainResults] = useState<string[]>([]);
  const [mainTaskOptions, setMainTaskOptions] = useState<TaskSummary[]>([]);
  const [mainTaskResults, setMainTaskResults] = useState<TaskRuntimeResult[]>([]);
  const [detailTaskId, setDetailTaskId] = useState("");
  const [runtime, setRuntime] = useState<DetailPageRuntimePayload | null>(null);
  const [message, setMessage] = useState("请先配置素材与商品信息");
  const [previewImage, setPreviewImage] = useState<DetailPageRuntimeImage | null>(null);
  const [submitting, setSubmitting] = useState<"plan" | "full" | "">("");

  useEffect(() => {
    fetchTasks().then((rows) => setMainTaskOptions(rows.filter((item) => item.task_type === "main_image").slice(0, 10))).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!mainTaskId) {
      setMainTaskResults([]);
      return;
    }
    fetchTaskRuntime(mainTaskId)
      .then((payload) => {
        setMainTaskResults(payload.results.filter((item) => item.status === "completed"));
      })
      .catch(() => setMainTaskResults([]));
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
        setMessage(data.message);
        if (data.status === "created" || data.status === "running") {
          timer = window.setTimeout(poll, POLL_INTERVAL_MS);
        }
      } catch {
        if (!cancelled) {
          setMessage("详情图运行时获取失败");
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

  const parsedSellingPoints = useMemo(() => sellingPointsInput.split("\n").map((item) => item.trim()).filter(Boolean), [sellingPointsInput]);

  function updateFiles(role: AssetRole, files: FileList | null) {
    if (!files) return;
    setFileBuckets((prev) => ({ ...prev, [role]: [...prev[role], ...Array.from(files)] }));
  }

  function removeFile(role: AssetRole, index: number) {
    setFileBuckets((prev) => ({ ...prev, [role]: prev[role].filter((_, idx) => idx !== index) }));
  }

  async function submit(mode: "plan" | "full") {
    setSubmitting(mode);
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
      setMessage(`${mode === "plan" ? "规划" : "详情图"}任务已提交：${result.task_id}`);
    } catch {
      setMessage("提交失败，请检查参数");
    } finally {
      setSubmitting("");
    }
  }

  function resetForm() {
    setBrandName("");
    setProductName("");
    setTeaType("乌龙茶");
    setStyleNotes("");
    setExtraRequirements("");
    setBrewSuggestion("");
    setSellingPointsInput("");
    setSpecForm(emptySpec);
    setFileBuckets({ packaging: [], dry_leaf: [], tea_soup: [], leaf_bottom: [], scene_ref: [], bg_ref: [] });
    setSelectedMainResults([]);
    setRuntime(null);
    setDetailTaskId("");
    setMessage("已清空当前任务");
  }

  return (
    <PageShell activeKey="detail-pages">
      <PageHeader
        title="茶叶详情图生成"
        subtitle="独立详情图任务流：规划、文案、Prompt、生成、QC 与导出"
        actions={
          <div className="card-actions">
            <button className="btn-secondary" onClick={() => submit("plan")} disabled={submitting !== ""}>{submitting === "plan" ? "规划中..." : "生成详情图规划"}</button>
            <button className="btn-primary" onClick={() => submit("full")} disabled={submitting !== ""}>{submitting === "full" ? "生成中..." : "开始生成详情图"}</button>
          </div>
        }
      />
      <div className="detail-page-layout">
        <div className="detail-column-stack">
          <SectionCard title="素材输入区">
            <label>主图任务来源</label>
            <select className="input" value={mainTaskId} onChange={(event) => setMainTaskId(event.target.value)}>
              <option value="">不导入主图</option>
              {mainTaskOptions.map((item) => <option key={item.task_id} value={item.task_id}>{item.title || item.task_id}</option>)}
            </select>
            <button className="btn-secondary" onClick={() => { if (mainTaskOptions[0]) setMainTaskId(mainTaskOptions[0].task_id); }}>从最近主图任务导入</button>
            {mainTaskResults.length > 0 ? (
              <div className="detail-form-grid">
                {mainTaskResults.map((item) => (
                  <label key={item.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <input type="checkbox" checked={selectedMainResults.includes(item.file_name)} onChange={() => setSelectedMainResults((prev) => prev.includes(item.file_name) ? prev.filter((v) => v !== item.file_name) : [...prev, item.file_name])} />
                    <span>{item.title}</span>
                  </label>
                ))}
              </div>
            ) : null}
            <AssetUpload role="packaging" label="包装图" files={fileBuckets.packaging} onAdd={updateFiles} onRemove={removeFile} />
            <AssetUpload role="dry_leaf" label="茶干图" files={fileBuckets.dry_leaf} onAdd={updateFiles} onRemove={removeFile} />
            <AssetUpload role="tea_soup" label="茶汤图" files={fileBuckets.tea_soup} onAdd={updateFiles} onRemove={removeFile} />
            <AssetUpload role="leaf_bottom" label="叶底图" files={fileBuckets.leaf_bottom} onAdd={updateFiles} onRemove={removeFile} />
            <AssetUpload role="scene_ref" label="场景参考" files={fileBuckets.scene_ref} onAdd={updateFiles} onRemove={removeFile} />
            <AssetUpload role="bg_ref" label="背景参考" files={fileBuckets.bg_ref} onAdd={updateFiles} onRemove={removeFile} />
          </SectionCard>

          <SectionCard title="商品信息区">
            <input className="input" placeholder="品牌名" value={brandName} onChange={(event) => setBrandName(event.target.value)} />
            <input className="input" placeholder="商品名" value={productName} onChange={(event) => setProductName(event.target.value)} />
            <input className="input" placeholder="茶类" value={teaType} onChange={(event) => setTeaType(event.target.value)} />
            <label>平台</label><select className="input" value={platform} onChange={(event) => setPlatform(event.target.value)}><option value="tmall">天猫</option></select>
            <label>风格</label><select className="input" value={stylePreset} onChange={(event) => setStylePreset(event.target.value)}><option value="tea_tmall_premium_light">tea_tmall_premium_light</option></select>
            <input className="input" placeholder="价格带" value={priceBand} onChange={(event) => setPriceBand(event.target.value)} />
            <input className="input" placeholder="净含量" value={specForm.net_content} onChange={(event) => setSpecForm({ ...specForm, net_content: event.target.value })} />
            <input className="input" placeholder="产地" value={specForm.origin} onChange={(event) => setSpecForm({ ...specForm, origin: event.target.value })} />
            <input className="input" placeholder="配料" value={specForm.ingredients} onChange={(event) => setSpecForm({ ...specForm, ingredients: event.target.value })} />
            <input className="input" placeholder="保质期" value={specForm.shelf_life} onChange={(event) => setSpecForm({ ...specForm, shelf_life: event.target.value })} />
            <input className="input" placeholder="储存方式" value={specForm.storage} onChange={(event) => setSpecForm({ ...specForm, storage: event.target.value })} />
            <input className="input" placeholder="冲泡建议" value={brewSuggestion} onChange={(event) => setBrewSuggestion(event.target.value)} />
          </SectionCard>

          <SectionCard title="卖点与目标区">
            <textarea className="input" rows={5} value={sellingPointsInput} onChange={(event) => setSellingPointsInput(event.target.value)} placeholder="每行一个卖点" />
            <textarea className="input" rows={3} value={styleNotes} onChange={(event) => setStyleNotes(event.target.value)} placeholder="风格方向" />
            <textarea className="input" rows={3} value={extraRequirements} onChange={(event) => setExtraRequirements(event.target.value)} placeholder="补充要求" />
            <label>目标张数</label>
            <select className="input" value={String(targetSliceCount)} onChange={(event) => setTargetSliceCount(Number(event.target.value))}>{[4, 5, 6].map((item) => <option key={item} value={item}>{item}</option>)}</select>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}><input type="checkbox" checked={preferMainResultFirst} onChange={(event) => setPreferMainResultFirst(event.target.checked)} />优先引用主图结果</label>
            <div className="card-actions">
              <button className="btn-secondary" onClick={resetForm}>清空当前任务</button>
              <button className="btn-secondary" onClick={() => navigate("/main-images")}>回到主图工作台</button>
            </div>
          </SectionCard>
        </div>

        <SectionCard title="规划与结果预览区">
          <p className="card-meta">{message}</p>
          {runtime?.plan ? (
            <div className="detail-form-grid">
              {runtime.plan.pages.map((page) => (
                <div key={page.page_id} className="result-card" style={{ padding: 12 }}>
                  <strong>{page.title}</strong>
                  {page.screens.map((screen) => (
                    <p key={screen.screen_id} style={{ margin: "6px 0" }}>{screen.screen_id} · {screen.theme} · {screen.goal}</p>
                  ))}
                </div>
              ))}
            </div>
          ) : <div className="result-empty-state">先生成规划后可查看每张图对应的两屏主题与卖点目标。</div>}

          <h4>结果图</h4>
          <div className="result-grid">
            {runtime?.images.map((image) => (
              <article key={image.image_id} className="result-card">
                <button type="button" className="result-image-button" onClick={() => image.image_url && setPreviewImage(image)} disabled={!image.image_url}>
                  {image.image_url ? <img src={image.image_url} alt={image.title} className="result-image" /> : <div className="result-image result-image-placeholder">{image.status}</div>}
                </button>
                <div className="result-body">
                  <p className="result-title">{image.title}</p>
                  <p className="result-subtitle">参考：{image.reference_roles.join(" / ") || "待绑定"}</p>
                  {image.image_url ? <a className="btn-secondary btn-compact" href={image.image_url} download>下载单张</a> : null}
                </div>
              </article>
            ))}
          </div>

          {runtime?.copy_blocks?.length ? (
            <SectionCard title="文案结构化结果">
              {runtime.copy_blocks.slice(0, 8).map((item) => <p key={`${item.page_id}-${item.screen_id}`}>{item.screen_id}｜{item.headline}｜{item.subheadline}</p>)}
            </SectionCard>
          ) : null}
        </SectionCard>

        <SectionCard title="样式与运行信息区">
          <p className="card-meta">任务ID：{runtime?.task_id || detailTaskId || "-"}</p>
          <p className="card-meta">当前状态：{runtime?.status || "未开始"}</p>
          <p className="card-meta">当前阶段：{runtime?.current_stage_label || "-"}</p>
          <p className="card-meta">进度：{runtime?.progress_percent ?? 0}%</p>
          <p className="card-meta">已生成 / 计划：{runtime?.generated_count ?? 0} / {runtime?.planned_count ?? 0}</p>
          <p className="card-meta">模板：{runtime?.plan?.template_name || "tea_tmall_premium_v1"}</p>
          <p className="card-meta">风格锚点：{runtime?.plan?.global_style_anchor || "-"}</p>
          <p className="card-meta">QC：{runtime?.qc_summary.passed ? "通过" : "待复核"}，警告 {runtime?.qc_summary.warning_count ?? 0}</p>
          {runtime?.qc_summary.issues?.length ? <ul className="detail-tab-list">{runtime.qc_summary.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul> : null}
          {runtime?.export_zip_url ? <a className="btn-primary" href={runtime.export_zip_url} download>下载 ZIP</a> : null}
        </SectionCard>
      </div>

      {previewImage ? (
        <div className="preview-modal" role="dialog" aria-modal="true" onClick={() => setPreviewImage(null)}>
          <div className="preview-modal__content" onClick={(event) => event.stopPropagation()}>
            <img src={previewImage.image_url} alt={previewImage.title} className="preview-modal__image" />
            <div className="preview-modal__meta"><strong>{previewImage.title}</strong></div>
          </div>
        </div>
      ) : null}
    </PageShell>
  );
}

function AssetUpload({ role, label, files, onAdd, onRemove }: { role: AssetRole; label: string; files: File[]; onAdd: (role: AssetRole, files: FileList | null) => void; onRemove: (role: AssetRole, index: number) => void; }) {
  return (
    <div className="detail-form-grid">
      <label>{label}（{files.length}）</label>
      <input type="file" multiple onChange={(event) => onAdd(role, event.target.files)} />
      {files.map((file, index) => (
        <label key={`${file.name}-${index}`} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
          <span>{file.name}</span>
          <button type="button" className="btn-secondary btn-compact" onClick={() => onRemove(role, index)}>删除</button>
        </label>
      ))}
    </div>
  );
}
