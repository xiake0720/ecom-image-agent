import { useState } from "react";
import { PageHeader } from "../components/common/PageHeader";
import { SectionCard } from "../components/common/SectionCard";
import { PageShell } from "../components/layout/PageShell";
import { previewGroups, previewTasks } from "../mocks/previewCenterMock";

export function PreviewPage() {
  const [group, setGroup] = useState(previewGroups[0]);
  const [activeTaskId, setActiveTaskId] = useState(previewTasks[0].id);
  const active = previewTasks.find((item) => item.id === activeTaskId) ?? previewTasks[0];

  return (
    <PageShell activeKey="preview">
      <PageHeader title="预览中心" subtitle="集中查看主图、详情长图与导出文件" />
      <div style={{ display: "grid", gridTemplateColumns: "220px 320px 1fr", gap: 12 }}>
        <SectionCard title="任务分组">
          {previewGroups.map((item) => <button key={item} className="btn-secondary" style={{ width: "100%", marginBottom: 8, background: group === item ? "#eef3ff" : "#fff" }} onClick={() => setGroup(item)}>{item}</button>)}
        </SectionCard>
        <SectionCard title="任务列表">
          {previewTasks.map((task) => (
            <div key={task.id} style={{ border: "1px solid #dbe4f3", borderRadius: 10, padding: 8, marginBottom: 8, cursor: "pointer", background: task.id === activeTaskId ? "#f4f8ff" : "#fff" }} onClick={() => setActiveTaskId(task.id)}>
              <img src={task.cover} style={{ width: "100%", height: 80, objectFit: "cover", borderRadius: 8 }} />
              <p style={{ margin: "6px 0 0", fontWeight: 600 }}>{task.name}</p>
              <p style={{ margin: "4px 0 0", fontSize: 12, color: "#64748b" }}>{task.platform} · {task.status} · QC {task.qc}</p>
            </div>
          ))}
        </SectionCard>
        <SectionCard title="大图预览">
          <img src={active.cover} style={{ width: "100%", height: active.type === "detail" ? 520 : 360, objectFit: "cover", borderRadius: 12 }} />
          <p>文件名：{active.name}.png</p><p>尺寸：{active.type === "detail" ? "750x3200" : "1080x1440"}</p><p>平台：{active.platform}</p><p>QC 状态：{active.qc}</p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><button className="btn-primary">下载</button><button className="btn-secondary">重新生成</button><button className="btn-secondary">设为详情首图</button><button className="btn-secondary">进入详情页编辑</button></div>
        </SectionCard>
      </div>
    </PageShell>
  );
}
