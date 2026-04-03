import type { DetailPagePromptPlanItem } from "../../types/detail";

interface DetailPromptPreviewProps {
  promptPlan: DetailPagePromptPlanItem[];
}

/** Prompt 摘要预览区。 */
export function DetailPromptPreview({ promptPlan }: DetailPromptPreviewProps) {
  if (!promptPlan.length) {
    return <div className="detail-empty-state">生成 Prompt 后，这里会展示每张长图的引用关系、版式提示和 prompt 摘要。</div>;
  }

  return (
    <div className="detail-card-grid">
      {promptPlan.map((item) => (
        <article key={item.page_id} className="detail-prompt-card">
          <div className="detail-prompt-card__header">
            <strong>{item.page_title}</strong>
            <span>{item.target_width} × {item.target_height}</span>
          </div>
          <p className="detail-copy-muted">主题：{item.screen_themes.join(" / ")}</p>
          <p className="detail-copy-muted">引用：{item.references.map((ref) => ref.role).join(" / ") || "无"}</p>
          <ul className="detail-list">
            {item.layout_notes.map((note) => (
              <li key={`${item.page_id}-${note}`}>{note}</li>
            ))}
          </ul>
          <div className="detail-code-block">
            <strong>Prompt 摘要</strong>
            <p>{item.prompt.slice(0, 260)}{item.prompt.length > 260 ? "..." : ""}</p>
          </div>
          <div className="detail-code-block detail-code-block--negative">
            <strong>Negative Prompt</strong>
            <p>{item.negative_prompt}</p>
          </div>
        </article>
      ))}
    </div>
  );
}
