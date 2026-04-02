import { PageHeader } from "../components/common/PageHeader";
import { SectionCard } from "../components/common/SectionCard";
import { PageShell } from "../components/layout/PageShell";
import { dashboardStats, templateRank, trendData } from "../mocks/dashboardMock";

export function DashboardPage() {
  return (
    <PageShell activeKey="dashboard">
      <PageHeader title="数据中心" subtitle="统一查看任务产能、趋势与模板表现" />
      <div className="grid-4">
        {dashboardStats.map((item) => (
          <div className="stat-card" key={item.label}><p>{item.label}</p><strong>{item.value}</strong></div>
        ))}
      </div>
      <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "1.7fr 1fr", gap: 12 }}>
        <SectionCard title="近30天生成趋势">
          <div style={{ display: "grid", gridTemplateColumns: `repeat(${trendData.length},1fr)`, alignItems: "end", gap: 6, height: 180 }}>
            {trendData.map((n, idx) => <div key={idx} style={{ height: `${n}%`, background: "#8cb2ff", borderRadius: 6 }} />)}
          </div>
        </SectionCard>
        <SectionCard title="模板使用排行榜">
          {templateRank.map((name, idx) => <p key={name} style={{ margin: "8px 0" }}>{idx + 1}. {name}</p>)}
        </SectionCard>
      </div>
    </PageShell>
  );
}
