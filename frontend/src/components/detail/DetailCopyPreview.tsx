import type { DetailPageCopyBlock, DetailPagePlanPayload } from "../../types/detail";

interface DetailCopyPreviewProps {
  plan: DetailPagePlanPayload | null;
  copyBlocks: DetailPageCopyBlock[];
}

/** 文案预览区。 */
export function DetailCopyPreview({ plan, copyBlocks }: DetailCopyPreviewProps) {
  if (!plan || copyBlocks.length === 0) {
    return <div className="detail-empty-state">生成规划后，这里会按 screen 展示 headline、卖点和参数文案。</div>;
  }

  return (
    <div className="detail-stack">
      {plan.pages.map((page) => {
        const blocks = copyBlocks.filter((item) => item.page_id === page.page_id);
        return (
          <article key={page.page_id} className="detail-copy-panel">
            <div className="detail-copy-panel__header">
              <strong>{page.title}</strong>
              <span>{blocks.length} 个文案块</span>
            </div>
            <div className="detail-copy-grid">
              {blocks.map((block) => (
                <section key={`${block.page_id}:${block.screen_id}`} className="detail-copy-card">
                  <small>{block.screen_id}</small>
                  <h4>{block.headline || "待补标题"}</h4>
                  {block.subheadline ? <p className="detail-copy-subheadline">{block.subheadline}</p> : null}
                  {block.selling_points.length ? <p>{block.selling_points.join(" / ")}</p> : null}
                  {block.body_copy ? <p>{block.body_copy}</p> : null}
                  {block.parameter_copy ? <p className="detail-copy-muted">参数：{block.parameter_copy}</p> : null}
                  {block.cta_copy ? <p className="detail-copy-muted">CTA：{block.cta_copy}</p> : null}
                </section>
              ))}
            </div>
          </article>
        );
      })}
    </div>
  );
}
