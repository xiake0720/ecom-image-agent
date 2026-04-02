import { useMemo, useState } from "react";
import { PageHeader } from "../components/common/PageHeader";
import { SectionCard } from "../components/common/SectionCard";
import { PageShell } from "../components/layout/PageShell";
import { assetCategories, assetsMock, assetStats } from "../mocks/assetsLibraryMock";

export function AssetsLibraryPage() {
  const [category, setCategory] = useState("全部资源");
  const [query, setQuery] = useState("");
  const list = useMemo(() => assetsMock.filter((item) => (category === "全部资源" || item.category === category) && item.name.includes(query)), [category, query]);

  return (
    <PageShell activeKey="assets-library">
      <PageHeader title="资源库" subtitle="统一管理商品素材、背景参考图与生成结果" actions={<><button className="btn-secondary">批量导入</button><button className="btn-primary">上传素材</button></>} />
      <div className="filter-bar"><input placeholder="搜索资源" value={query} onChange={(e) => setQuery(e.target.value)} /><select><option>平台</option><option>天猫</option></select><select><option>商品</option></select><select><option>时间</option></select><select><option>标签</option></select></div>
      <div className="grid-4" style={{ marginBottom: 12 }}>{assetStats.map((s) => <div className="stat-card" key={s.label}><p>{s.label}</p><strong>{s.value}</strong></div>)}</div>
      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 12 }}>
        <SectionCard>{assetCategories.map((item) => <button key={item} className="btn-secondary" style={{ width: "100%", marginBottom: 8, background: category === item ? "#eef3ff" : "#fff" }} onClick={() => setCategory(item)}>{item}</button>)}</SectionCard>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: 12 }}>
          {list.map((item) => <SectionCard key={item.id}><img src={item.cover} style={{ width: "100%", height: 120, borderRadius: 10 }} /><p style={{ fontWeight: 600 }}>{item.name}</p><p style={{ color: "#64748b", fontSize: 12 }}>{item.size} · {item.date}</p><p style={{ color: "#64748b", fontSize: 12 }}>{item.tags} · {item.source}</p><div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}><button className="btn-secondary">预览</button><button className="btn-secondary">重命名</button><button className="btn-secondary">加入任务</button><button className="btn-secondary">删除</button></div></SectionCard>)}
        </div>
      </div>
    </PageShell>
  );
}
