import { useState } from "react";
import { PageHeader } from "../components/common/PageHeader";
import { SectionCard } from "../components/common/SectionCard";
import { PageShell } from "../components/layout/PageShell";
import { modelRouteDefaults, settingMenus } from "../mocks/settingsMock";

export function SettingsPage() {
  const [menu, setMenu] = useState("模型路由");
  const [form, setForm] = useState(modelRouteDefaults);

  return (
    <PageShell activeKey="settings">
      <PageHeader title="系统设置" subtitle="管理模型路由、导出规则与平台策略" />
      <div className="settings-layout">
        <SectionCard>
          <div className="sidebar-menu">
            {settingMenus.map((item) => (
              <button key={item} className={`btn-secondary ${menu === item ? "is-active" : ""}`} onClick={() => setMenu(item)}>
                {item}
              </button>
            ))}
          </div>
        </SectionCard>
        <SectionCard title={`${menu}配置`}>
          <div className="settings-content-grid">
            <label className="settings-field">
              语言模型
              <input className="input" value={form.llm} onChange={(event) => setForm({ ...form, llm: event.target.value })} />
            </label>
            <label className="settings-field">
              图像模型
              <input className="input" value={form.imageModel} onChange={(event) => setForm({ ...form, imageModel: event.target.value })} />
            </label>
            <label className="settings-field">
              默认画幅
              <input className="input" value={form.ratio} onChange={(event) => setForm({ ...form, ratio: event.target.value })} />
            </label>
            <label className="settings-field">
              默认出图
              <input className="input" value={String(form.count)} onChange={(event) => setForm({ ...form, count: Number(event.target.value) || 1 })} />
            </label>
            <label className="settings-field">
              详情模板
              <input className="input" value={form.detailTemplate} onChange={(event) => setForm({ ...form, detailTemplate: event.target.value })} />
            </label>
            <label className="settings-field">
              切片规则
              <input className="input" value={form.sliceRule} onChange={(event) => setForm({ ...form, sliceRule: event.target.value })} />
            </label>
          </div>
          <p className="settings-note">实时预览：{form.llm} + {form.imageModel}，{form.ratio}，{form.count} 张。</p>
          <div className="settings-actions">
            <button className="btn-primary">保存设置</button>
          </div>
        </SectionCard>
      </div>
    </PageShell>
  );
}
