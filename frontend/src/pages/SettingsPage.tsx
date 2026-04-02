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
      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 12 }}>
        <SectionCard>
          {settingMenus.map((item) => (
            <button key={item} className="btn-secondary" style={{ width: "100%", marginBottom: 8, background: menu === item ? "#eef3ff" : "#fff" }} onClick={() => setMenu(item)}>{item}</button>
          ))}
        </SectionCard>
        <SectionCard title={`${menu}配置`}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: 10 }}>
            <label>语言模型<input className="input" value={form.llm} onChange={(e) => setForm({ ...form, llm: e.target.value })} /></label>
            <label>图像模型<input className="input" value={form.imageModel} onChange={(e) => setForm({ ...form, imageModel: e.target.value })} /></label>
            <label>默认画幅<input className="input" value={form.ratio} onChange={(e) => setForm({ ...form, ratio: e.target.value })} /></label>
            <label>默认出图<input className="input" value={String(form.count)} onChange={(e) => setForm({ ...form, count: Number(e.target.value) || 1 })} /></label>
            <label>详情模板<input className="input" value={form.detailTemplate} onChange={(e) => setForm({ ...form, detailTemplate: e.target.value })} /></label>
            <label>切片规则<input className="input" value={form.sliceRule} onChange={(e) => setForm({ ...form, sliceRule: e.target.value })} /></label>
          </div>
          <p style={{ color: "#64748b" }}>实时预览：{form.llm} + {form.imageModel}，{form.ratio}，{form.count} 张。</p>
          <button className="btn-primary">保存设置</button>
        </SectionCard>
      </div>
    </PageShell>
  );
}
