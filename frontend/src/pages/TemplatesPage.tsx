import { useMemo, useState } from "react";
import { PageHeader } from "../components/common/PageHeader";
import { SectionCard } from "../components/common/SectionCard";
import { PageShell } from "../components/layout/PageShell";
import { templateCategories, templateList } from "../mocks/templateCenterMock";

export function TemplatesPage() {
  const [category, setCategory] = useState("全部模板");
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState("全部");

  const list = useMemo(() => templateList.filter((item) => (category === "全部模板" || item.type === category || (category === "我的模板" && item.id.endsWith("1"))) && (platform === "全部" || item.platform === platform) && item.name.includes(query)), [category, query, platform]);

  return (
    <PageShell activeKey="templates">
      <PageHeader title="模板中心" subtitle="管理主图模板与详情长图模板" actions={<><button className="btn-secondary">导入模板</button><button className="btn-primary">新建模板</button></>} />
      <div className="filter-bar"><select value={platform} onChange={(e) => setPlatform(e.target.value)}><option>全部</option><option>天猫</option><option>京东</option><option>拼多多</option><option>TikTok</option></select><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索模板" /></div>
      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 12 }}>
        <SectionCard>
          {templateCategories.map((item) => <button key={item} className="btn-secondary" style={{ width: "100%", marginBottom: 8, background: category === item ? "#eef3ff" : "#fff" }} onClick={() => setCategory(item)}>{item}</button>)}
        </SectionCard>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))", gap: 12 }}>
          {list.map((item) => (
            <SectionCard key={item.id}>
              <img src={item.cover} alt={item.name} style={{ width: "100%", height: 140, objectFit: "cover", borderRadius: 10 }} />
              <p style={{ fontWeight: 600 }}>{item.name}</p>
              <p style={{ color: "#64748b", fontSize: 13 }}>{item.platform} · {item.type} · {item.style}</p>
              <p style={{ color: "#64748b", fontSize: 12 }}>更新：{item.updatedAt} · 使用 {item.usage}</p>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}><button className="btn-secondary">预览</button><button className="btn-secondary">复制</button><button className="btn-secondary">编辑</button><button className="btn-primary">启用</button></div>
            </SectionCard>
          ))}
        </div>
      </div>
    </PageShell>
  );
}
