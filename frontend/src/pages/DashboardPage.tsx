import { PageHeader } from "../components/common/PageHeader";
import { SectionCard } from "../components/common/SectionCard";
import { PageShell } from "../components/layout/PageShell";
import { dashboardStats, templateRank, trendData } from "../mocks/dashboardMock";

const platformDistribution = [
  { name: "天猫", value: 42 },
  { name: "京东", value: 27 },
  { name: "拼多多", value: 19 },
  { name: "抖音", value: 12 },
];

export function DashboardPage() {
  return (
    <PageShell activeKey="dashboard">
      <PageHeader title="数据中心" subtitle="统一查看任务产能、趋势与模板表现" />
      <div className="grid-4">
        {dashboardStats.map((item) => (
          <div className="stat-card" key={item.label}>
            <p>{item.label}</p>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>
      <div className="dashboard-chart-layout">
        <SectionCard title="近30天生成趋势">
          <div className="trend-bars" style={{ gridTemplateColumns: `repeat(${trendData.length}, 1fr)` }}>
            {trendData.map((item, idx) => (
              <div key={idx} className="bar" style={{ height: `${item}%` }} />
            ))}
          </div>
        </SectionCard>
        <SectionCard title="模板使用排行榜">
          <ol className="rank-list">
            {templateRank.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        </SectionCard>
      </div>
      <div className="dashboard-mini-layout">
        <SectionCard title="平台分布">
          {platformDistribution.map((item) => (
            <div key={item.name} style={{ display: "grid", gridTemplateColumns: "72px 1fr 40px", gap: 10, alignItems: "center", marginBottom: 10 }}>
              <span>{item.name}</span>
              <div style={{ height: 10, borderRadius: 999, background: "#e2e8f7", overflow: "hidden" }}>
                <div style={{ width: `${item.value}%`, height: "100%", background: "#7ea5ff" }} />
              </div>
              <strong style={{ fontSize: 13, color: "#334155" }}>{item.value}%</strong>
            </div>
          ))}
        </SectionCard>
        <SectionCard title="任务看板摘要">
          <p className="card-meta" style={{ marginTop: 0 }}>今日完成任务 128，平均耗时 2 分 34 秒，质检告警 6 条。</p>
          <p className="card-meta">当前排队任务 17，峰值时间段为 13:00 - 15:00，可优先启用高速模型路由。</p>
        </SectionCard>
      </div>
    </PageShell>
  );
}
