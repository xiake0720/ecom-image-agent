import { useMemo, useState } from "react";
import { http } from "../services/http";
import "./MainImagePage.css";

type ResultStatus = "completed" | "queued" | "running" | "failed";

interface ResultCard {
  id: string;
  title: string;
  subtitle: string;
  imageUrl: string;
  status: ResultStatus;
}

const STYLE_TAGS = ["简洁", "自然", "优选", "佳节", "轻奢", "质感", "暖调", "极简"];
const PLATFORMS = ["天猫", "京东", "拼多多", "抖音"];

/**
 * 主图生成工作台页面。
 * 职责：在不改变后端接口逻辑的前提下，提供统一且可扩展的工作台 UI 壳层。
 * 上下游关系：向后端提交 multipart（white_bg + product_name），并在页面右侧展示任务进度与结果占位。
 */
export function MainImagePage() {
  const [productName, setProductName] = useState("");
  const [whiteBg, setWhiteBg] = useState<File | null>(null);
  const [referenceImages, setReferenceImages] = useState<File[]>([]);
  const [platform, setPlatform] = useState("天猫");
  const [selectedStyles, setSelectedStyles] = useState<string[]>(["简洁", "自然"]);
  const [quality, setQuality] = useState(72);
  const [brightness, setBrightness] = useState(50);
  const [ratio, setRatio] = useState("3:4");
  const [format, setFormat] = useState("PNG");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("未提交");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const previewUrl = useMemo(() => (whiteBg ? URL.createObjectURL(whiteBg) : ""), [whiteBg]);

  const resultCards: ResultCard[] = [
    { id: "1", title: "风格 A", subtitle: "场景 B", imageUrl: "https://images.unsplash.com/photo-1523293182086-7651a899d37f?auto=format&fit=crop&w=640&q=80", status: "completed" },
    { id: "2", title: "风格 A", subtitle: "场景 C", imageUrl: "https://images.unsplash.com/photo-1541643600914-78b084683601?auto=format&fit=crop&w=640&q=80", status: "completed" },
    { id: "3", title: "风格 B", subtitle: "场景 A", imageUrl: "https://images.unsplash.com/photo-1611930022073-b7a4ba5fcccd?auto=format&fit=crop&w=640&q=80", status: "running" },
    { id: "4", title: "风格 C", subtitle: "场景 D", imageUrl: "https://images.unsplash.com/photo-1611080626919-7cf5a9dbab5b?auto=format&fit=crop&w=640&q=80", status: "queued" },
    { id: "5", title: "风格 D", subtitle: "场景 E", imageUrl: "https://images.unsplash.com/photo-1585386959984-a4155223168f?auto=format&fit=crop&w=640&q=80", status: "completed" },
    { id: "6", title: "风格 E", subtitle: "场景 F", imageUrl: "https://images.unsplash.com/photo-1600959907703-125ba1374a12?auto=format&fit=crop&w=640&q=80", status: "queued" },
  ];

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

  async function submit() {
    if (!whiteBg) {
      setMessage("请先上传商品白底图");
      return;
    }
    setIsSubmitting(true);
    try {
      const form = new FormData();
      form.append("product_name", productName);
      form.append("white_bg", whiteBg);
      const resp = await http.post("/image/generate-main", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setMessage(`任务已提交：${resp.data.data.task_id}`);
    } catch {
      setMessage("提交失败，请稍后重试");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="main-workbench">
      {/* 顶部导航：固定三段式信息层级，避免页面内容拥挤无主次 */}
      <header className="workbench-topbar">
        <div className="brand-block">
          <div className="brand-logo">E</div>
          <div className="brand-text">
            <strong>ECOM_AI</strong>
            <span>AI 电商图片生成平台</span>
          </div>
        </div>
        <nav className="top-nav" aria-label="主导航">
          <a className="active" href="#" onClick={(e) => e.preventDefault()}>
            工作台
          </a>
          <a href="#" onClick={(e) => e.preventDefault()}>
            模板中心
          </a>
          <a href="#" onClick={(e) => e.preventDefault()}>
            资源库
          </a>
          <a href="#" onClick={(e) => e.preventDefault()}>
            数据中心
          </a>
        </nav>
        <div className="top-actions">
          <span className="status-pill status-running">生成中</span>
          <button type="button" className="icon-btn" aria-label="通知">
            <BellIcon />
          </button>
          <button type="button" className="icon-btn" aria-label="设置">
            <GearIcon />
          </button>
        </div>
      </header>

      <main className="workbench-content">
        {/* 左侧操作面板：严格按规范顺序组织输入流程 */}
        <section className="left-panel">
          <article className="panel-card">
            <h3>上传商品图</h3>
            <div className="upload-row">
              <label className="upload-dropzone" htmlFor="white-bg-upload">
                <span>上传商品图</span>
                <small>JPG / PNG / WebP</small>
              </label>
              <input
                id="white-bg-upload"
                type="file"
                accept="image/*"
                onChange={(e) => setWhiteBg(e.target.files?.[0] ?? null)}
                hidden
              />
              <div className="upload-preview">
                {previewUrl ? <img src={previewUrl} alt="商品图预览" /> : <span>暂无预览</span>}
              </div>
            </div>
          </article>

          <article className="panel-card">
            <h3>上传参考图</h3>
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={(e) => setReferenceImages(Array.from(e.target.files ?? []))}
            />
            <p className="hint">已选择 {referenceImages.length} 张参考图，用于风格/构图提示。</p>
          </article>

          <article className="panel-card">
            <h3>选择平台</h3>
            <div className="radio-group">
              {PLATFORMS.map((item) => (
                <label key={item} className={`radio-item ${platform === item ? "checked" : ""}`}>
                  <input type="radio" name="platform" checked={platform === item} onChange={() => setPlatform(item)} />
                  {item}
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
            <p className="hint">建议选择不超过 5 个风格标签。</p>
          </article>

          <article className="panel-card">
            <h3>参数设置</h3>
            <div className="form-grid">
              <label>
                质量 {quality}
                <input type="range" min={10} max={100} value={quality} onChange={(e) => setQuality(Number(e.target.value))} />
              </label>
              <label>
                明朗度 {brightness}
                <input type="range" min={0} max={100} value={brightness} onChange={(e) => setBrightness(Number(e.target.value))} />
              </label>
              <label>
                画面比例
                <select value={ratio} onChange={(e) => setRatio(e.target.value)}>
                  <option>3:4</option>
                  <option>1:1</option>
                  <option>16:9</option>
                </select>
              </label>
              <label>
                导出格式
                <select value={format} onChange={(e) => setFormat(e.target.value)}>
                  <option>PNG</option>
                  <option>JPG</option>
                  <option>WEBP</option>
                </select>
              </label>
            </div>
          </article>

          <article className="panel-card">
            <h3>文案备注</h3>
            <textarea
              placeholder="请输入品牌名、核心卖点或禁用词"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={200}
            />
            <div className="text-meta">{note.length}/200</div>
            <div className="actions-row">
              <button className="btn-primary" onClick={submit} disabled={isSubmitting}>
                {isSubmitting ? "生成中..." : "开始生成"}
              </button>
              <button className="btn-secondary" type="button">
                生成详情页方案
              </button>
            </div>
            <p className="submit-message">{message}</p>
          </article>
        </section>

        {/* 右侧任务进度与结果区：上进度、下三列卡片 */}
        <section className="right-panel">
          <article className="panel-card progress-card">
            <h3>任务进度总览</h3>
            <div className="progress-track" role="progressbar" aria-valuenow={68} aria-valuemin={0} aria-valuemax={100}>
              <div className="progress-fill" style={{ width: "68%" }} />
            </div>
            <div className="stage-row">
              <span className="active">解析商品</span>
              <span className="active">风格匹配</span>
              <span className="active">生成迭代</span>
              <span>质检</span>
              <span>完成</span>
            </div>
            <p className="hint">正在生成第 3 / 8 张图片...</p>
          </article>

          <div className="result-grid">
            {resultCards.map((card) => (
              <article key={card.id} className="result-card">
                <img src={card.imageUrl} alt={`结果图 ${card.id}`} />
                <div className="result-meta">
                  <span className={`status-pill status-${card.status}`}>{statusLabel(card.status)}</span>
                  <div className="result-actions">
                    <button type="button" className="icon-btn" aria-label="预览">
                      <EyeIcon />
                    </button>
                    <button type="button" className="icon-btn" aria-label="下载">
                      <DownloadIcon />
                    </button>
                    <button type="button" className="icon-btn" aria-label="重试">
                      <RefreshIcon />
                    </button>
                  </div>
                </div>
                <p className="result-title">
                  {card.title}，{card.subtitle}
                </p>
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

function statusLabel(status: ResultStatus): string {
  if (status === "completed") return "完成";
  if (status === "queued") return "队列中";
  if (status === "running") return "生成中";
  return "失败";
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
