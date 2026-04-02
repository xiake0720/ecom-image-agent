import { useMemo, useState } from "react";
import { PageHeader } from "../components/common/PageHeader";
import { SectionCard } from "../components/common/SectionCard";
import { PageShell } from "../components/layout/PageShell";
import { detailFormMock, detailLogs, moduleToggleMock, sellingPointsMock } from "../mocks/detailEditorMock";

export function DetailPageGeneratorPage() {
  const [form, setForm] = useState(detailFormMock);
  const [points, setPoints] = useState(sellingPointsMock);
  const [activeTab, setActiveTab] = useState<"logs" | "version" | "qc">("logs");
  const [modules, setModules] = useState<Record<string, boolean>>(Object.fromEntries(moduleToggleMock.map((item) => [item, true])));

  const tabList = useMemo(
    () => (activeTab === "logs" ? detailLogs.logs : activeTab === "version" ? detailLogs.versions : detailLogs.qc),
    [activeTab],
  );

  return (
    <PageShell activeKey="detail-pages">
      <PageHeader title="详情长图编辑" subtitle="左侧内容配置 + 中间实时预览 + 右侧样式策略" actions={<button className="btn-primary">生成详情长图</button>} />
      <div className="detail-page-layout">
        <div className="detail-column-stack">
          <SectionCard title="已选主图">
            <img src="/mock/main-1.svg" alt="已选主图" style={{ width: "100%", height: 180, borderRadius: 10, objectFit: "cover" }} />
            <div className="card-actions">
              <button className="btn-secondary">更换首图</button>
              <button className="btn-secondary">从主图结果选择</button>
            </div>
          </SectionCard>
          <SectionCard title="商品参数">
            <div className="detail-form-grid">
              {Object.entries(form).map(([key, value]) => (
                <input
                  key={key}
                  className="input"
                  value={value}
                  onChange={(event) => setForm({ ...form, [key]: event.target.value })}
                  style={{ width: "100%" }}
                />
              ))}
            </div>
          </SectionCard>
          <SectionCard title="卖点模块">
            <div className="detail-form-grid">
              {points.map((item, idx) => (
                <input
                  key={idx}
                  className="input"
                  value={item}
                  style={{ width: "100%" }}
                  onChange={(event) => setPoints(points.map((point, pointIdx) => (pointIdx === idx ? event.target.value : point)))}
                />
              ))}
            </div>
          </SectionCard>
          <SectionCard title="模块开关">
            <div className="detail-form-grid">
              {moduleToggleMock.map((item) => (
                <label key={item} style={{ display: "flex", alignItems: "center", gap: 8, color: "#334155", fontSize: 14 }}>
                  <input type="checkbox" checked={modules[item]} onChange={() => setModules({ ...modules, [item]: !modules[item] })} />
                  {item}
                </label>
              ))}
            </div>
          </SectionCard>
        </div>

        <SectionCard title="实时预览（长图画布）">
          <div className="detail-preview-shell">
            <div className="detail-preview-canvas">
              <img src="/mock/detail-hero.svg" alt="详情首屏" />
              <h3>{form.productName}</h3>
              {modules["卖点模块"] ? points.map((point) => <p key={point}>• {point}</p>) : null}
              <img src="/mock/detail-tea.svg" alt="详情茶叶图" />
              {modules["参数模块"] ? (
                <table>
                  <tbody>
                    {Object.entries(form)
                      .slice(1, 7)
                      .map(([key, value]) => (
                        <tr key={key}>
                          <td>{key}</td>
                          <td>{value}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              ) : null}
              <p>冲泡建议：{form.brew}</p>
              <p>发货说明：48小时内发货，破损包赔。</p>
            </div>
          </div>
          <div className="detail-tab-actions">
            <button className={activeTab === "logs" ? "btn-primary" : "btn-secondary"} onClick={() => setActiveTab("logs")}>生成日志</button>
            <button className={activeTab === "version" ? "btn-primary" : "btn-secondary"} onClick={() => setActiveTab("version")}>历史版本</button>
            <button className={activeTab === "qc" ? "btn-primary" : "btn-secondary"} onClick={() => setActiveTab("qc")}>QC检查</button>
          </div>
          <ul className="detail-tab-list">{tabList.map((item) => <li key={item}>{item}</li>)}</ul>
        </SectionCard>

        <SectionCard title="样式设置">
          <p className="card-meta" style={{ marginTop: 0 }}>模板风格</p>
          <select className="input" style={{ width: "100%" }}>
            <option>天猫高端版</option>
            <option>拼多多转化版</option>
            <option>京东清晰版</option>
          </select>
          <p className="card-meta">色彩样式</p>
          <div className="detail-form-grid">
            <input className="input" defaultValue="#2f5aff" style={{ width: "100%" }} />
            <input className="input" defaultValue="#6ba2ff" style={{ width: "100%" }} />
            <input className="input" defaultValue="#f5f8ff" style={{ width: "100%" }} />
          </div>
          <p className="card-meta">字体层级</p>
          <div className="detail-form-grid">
            <input className="input" defaultValue="标题 34" style={{ width: "100%" }} />
            <input className="input" defaultValue="正文 16" style={{ width: "100%" }} />
            <input className="input" defaultValue="参数表清晰" style={{ width: "100%" }} />
          </div>
          <p className="card-meta">平台提示：宽度 750px，建议切片 6-8 张，参数完整度建议 ≥ 95%。</p>
        </SectionCard>
      </div>
    </PageShell>
  );
}
