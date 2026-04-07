import type { DetailPagePlanPayload, DetailPagePromptPlanItem } from "../../types/detail";

interface DetailPlanPreviewProps {
  plan: DetailPagePlanPayload | null;
  promptPlan: DetailPagePromptPlanItem[];
  message: string;
}

/** 规划预览区。 */
export function DetailPlanPreview({ plan, promptPlan, message }: DetailPlanPreviewProps) {
  if (!plan) {
    return <div className="detail-empty-state">{message}</div>;
  }

  return (
    <div className="detail-stack">
      <div className="detail-summary-strip">
        <span>共 {plan.total_pages} 张 3:4 单屏图</span>
        <span>{plan.total_screens} 屏内容</span>
        <span>{plan.global_style_anchor}</span>
      </div>

      <div className="detail-card-grid">
        {plan.pages.map((page) => {
          const prompt = promptPlan.find((item) => item.page_id === page.page_id);
          return (
            <article key={page.page_id} className="detail-preview-card">
              <div className="detail-preview-card__header">
                <strong>{page.title}</strong>
                <span>{page.page_id}</span>
              </div>
              <div className="detail-preview-card__body">
                {page.screens.map((screen) => (
                  <div key={screen.screen_id} className="detail-screen-row">
                    <div>
                      <small>{screen.screen_id}</small>
                      <strong>{screen.theme}</strong>
                    </div>
                    <p>{screen.goal}</p>
                  </div>
                ))}
              </div>
              <div className="detail-preview-card__footer">
                <span>建议素材：{page.screens.flatMap((screen) => screen.suggested_asset_roles).join(" / ")}</span>
                <span>实际绑定：{prompt?.references.map((ref) => ref.role).join(" / ") || "待生成"}</span>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
