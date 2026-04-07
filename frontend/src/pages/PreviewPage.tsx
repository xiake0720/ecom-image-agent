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
      <PageHeader title="预览中心" subtitle="集中查看主图、详情图与导出文件" />
      <div className="preview-layout">
        <SectionCard title="任务分组">
          <div className="sidebar-menu">
            {previewGroups.map((item) => (
              <button key={item} className={`btn-secondary ${group === item ? "is-active" : ""}`} onClick={() => setGroup(item)}>
                {item}
              </button>
            ))}
          </div>
        </SectionCard>
        <SectionCard title="任务列表">
          <div className="preview-task-list">
            {previewTasks.map((task) => (
              <div key={task.id} className={`preview-task-item ${task.id === activeTaskId ? "is-active" : ""}`} onClick={() => setActiveTaskId(task.id)}>
                <img src={task.cover} alt={task.name} />
                <p className="card-title">{task.name}</p>
                <p className="card-meta">{task.platform} · {task.status} · QC {task.qc}</p>
              </div>
            ))}
          </div>
        </SectionCard>
        <SectionCard title="大图预览">
          <img src={active.cover} alt={active.name} className={`preview-main-image ${active.type === "detail" ? "is-detail" : "is-main"}`} />
          <div className="preview-file-meta">
            <p>文件名：{active.name}.png</p>
            <p>尺寸：{active.type === "detail" ? "750x3200" : "1080x1440"}</p>
            <p>平台：{active.platform}</p>
            <p>QC 状态：{active.qc}</p>
          </div>
          <div className="card-actions">
            <button className="btn-primary">下载</button>
            <button className="btn-secondary">重新生成</button>
            <button className="btn-secondary">设为详情首图</button>
            <button className="btn-secondary">进入详情页编辑</button>
          </div>
        </SectionCard>
      </div>
    </PageShell>
  );
}
