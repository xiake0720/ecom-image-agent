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
      <PageHeader
        title="资源库"
        subtitle="统一管理商品素材、背景参考图与生成结果"
        actions={
          <>
            <button className="btn-secondary">批量导入</button>
            <button className="btn-primary">上传素材</button>
          </>
        }
      />
      <div className="filter-bar">
        <input placeholder="搜索资源" value={query} onChange={(event) => setQuery(event.target.value)} />
        <select>
          <option>平台</option>
          <option>天猫</option>
        </select>
        <select>
          <option>商品</option>
        </select>
        <select>
          <option>时间</option>
        </select>
        <select>
          <option>标签</option>
        </select>
      </div>
      <div className="grid-4" style={{ marginBottom: 12 }}>
        {assetStats.map((item) => (
          <div className="stat-card" key={item.label}>
            <p>{item.label}</p>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>
      <div className="page-two-col assets-content">
        <SectionCard>
          <div className="sidebar-menu">
            {assetCategories.map((item) => (
              <button key={item} className={`btn-secondary ${category === item ? "is-active" : ""}`} onClick={() => setCategory(item)}>
                {item}
              </button>
            ))}
          </div>
        </SectionCard>
        <div className="assets-grid">
          {list.map((item) => (
            <SectionCard key={item.id}>
              <img src={item.cover} alt={item.name} className="asset-card-cover" />
              <p className="card-title">{item.name}</p>
              <p className="card-meta">{item.size} · {item.date}</p>
              <p className="card-meta">{item.tags} · {item.source}</p>
              <div className="card-actions">
                <button className="btn-secondary">预览</button>
                <button className="btn-secondary">重命名</button>
                <button className="btn-secondary">加入任务</button>
                <button className="btn-secondary">删除</button>
              </div>
            </SectionCard>
          ))}
        </div>
      </div>
    </PageShell>
  );
}
