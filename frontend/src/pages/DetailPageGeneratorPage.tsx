import { useMemo, useState } from "react";
import { PageHeader } from "../components/common/PageHeader";
import { SectionCard } from "../components/common/SectionCard";
import { PageShell } from "../components/layout/PageShell";
import { detailFormMock, detailLogs, moduleToggleMock, sellingPointsMock } from "../mocks/detailEditorMock";

export function DetailPageGeneratorPage() {
  const [form, setForm] = useState(detailFormMock);
  const [points, setPoints] = useState(sellingPointsMock);
  const [activeTab, setActiveTab] = useState<"logs" | "version" | "qc">("logs");
  const [modules, setModules] = useState<Record<string, boolean>>(Object.fromEntries(moduleToggleMock.map((i) => [i, true])));

  const tabList = useMemo(() => activeTab === "logs" ? detailLogs.logs : activeTab === "version" ? detailLogs.versions : detailLogs.qc, [activeTab]);

  return (
    <PageShell activeKey="detail-pages">
      <PageHeader title="详情长图编辑" subtitle="左侧内容配置 + 中间实时预览 + 右侧样式策略" actions={<button className="btn-primary">生成详情长图</button>} />
      <div style={{ display: "grid", gridTemplateColumns: "360px 1fr 320px", gap: 12 }}>
        <div style={{ display: "grid", gap: 12, alignSelf: "start" }}>
          <SectionCard title="已选主图"><img src="/mock/main-1.svg" style={{ width: "100%", height: 150, borderRadius: 10 }} /><div style={{ display: "flex", gap: 8, marginTop: 10 }}><button className="btn-secondary">更换首图</button><button className="btn-secondary">从主图结果选择</button></div></SectionCard>
          <SectionCard title="商品参数">
            {Object.entries(form).map(([key, value]) => <input key={key} className="input" value={value} onChange={(e) => setForm({ ...form, [key]: e.target.value })} style={{ width: "100%", marginBottom: 8 }} />)}
          </SectionCard>
          <SectionCard title="卖点模块">
            {points.map((item, idx) => <input key={idx} className="input" value={item} style={{ width: "100%", marginBottom: 8 }} onChange={(e) => setPoints(points.map((p, pidx) => pidx === idx ? e.target.value : p))} />)}
          </SectionCard>
          <SectionCard title="模块开关">
            {moduleToggleMock.map((m) => <label key={m} style={{ display: "block", marginBottom: 6 }}><input type="checkbox" checked={modules[m]} onChange={() => setModules({ ...modules, [m]: !modules[m] })} /> {m}</label>)}
          </SectionCard>
        </div>
        <SectionCard title="实时预览（长图画布）">
          <div style={{ margin: "0 auto", width: 420, background: "#f8fafc", border: "1px solid #d9e4f8", borderRadius: 16, padding: 14 }}>
            <img src="/mock/detail-hero.svg" style={{ width: "100%", borderRadius: 10 }} />
            <h3>{form.productName}</h3>
            {modules["卖点模块"] ? points.map((p) => <p key={p}>• {p}</p>) : null}
            <img src="/mock/detail-tea.svg" style={{ width: "100%", borderRadius: 10 }} />
            {modules["参数模块"] ? <table style={{ width: "100%", background: "#fff", borderCollapse: "collapse" }}><tbody>{Object.entries(form).slice(1, 7).map(([k, v]) => <tr key={k}><td style={{ border: "1px solid #dbe4f2", padding: 6 }}>{k}</td><td style={{ border: "1px solid #dbe4f2", padding: 6 }}>{v}</td></tr>)}</tbody></table> : null}
            <p>冲泡建议：{form.brew}</p><p>发货说明：48小时内发货，破损包赔。</p>
          </div>
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <button className={activeTab === "logs" ? "btn-primary" : "btn-secondary"} onClick={() => setActiveTab("logs")}>生成日志</button>
            <button className={activeTab === "version" ? "btn-primary" : "btn-secondary"} onClick={() => setActiveTab("version")}>历史版本</button>
            <button className={activeTab === "qc" ? "btn-primary" : "btn-secondary"} onClick={() => setActiveTab("qc")}>QC检查</button>
          </div>
          <ul>{tabList.map((item) => <li key={item}>{item}</li>)}</ul>
        </SectionCard>
        <SectionCard title="样式设置">
          <p>模板风格</p><select className="input" style={{ width: "100%" }}><option>天猫高端版</option><option>拼多多转化版</option><option>京东清晰版</option></select>
          <p>色彩样式</p><input className="input" defaultValue="#2f5aff" style={{ width: "100%", marginBottom: 8 }} /><input className="input" defaultValue="#6ba2ff" style={{ width: "100%", marginBottom: 8 }} /><input className="input" defaultValue="#f5f8ff" style={{ width: "100%" }} />
          <p>字体层级</p><input className="input" defaultValue="标题 34" style={{ width: "100%", marginBottom: 8 }} /><input className="input" defaultValue="正文 16" style={{ width: "100%", marginBottom: 8 }} /><input className="input" defaultValue="参数表清晰" style={{ width: "100%" }} />
          <p style={{ color: "#64748b" }}>平台提示：宽度 750px，建议切片 6-8 张，参数完整度建议 ≥ 95%。</p>
        </SectionCard>
      </div>
    </PageShell>
  );
}
