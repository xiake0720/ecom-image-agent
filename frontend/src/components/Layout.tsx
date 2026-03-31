import { Link, Outlet } from "react-router-dom";

/**
 * 工作台主布局。
 * 输入：路由子页面。
 * 输出：统一导航壳层，保持页面结构一致。
 */
export function Layout() {
  return (
    <div style={{ fontFamily: "sans-serif", padding: 16 }}>
      <h1>电商图工作台</h1>
      <nav style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        <Link to="/">工作台</Link>
        <Link to="/main-images">主图生成</Link>
        <Link to="/detail-pages">详情页生成</Link>
        <Link to="/templates">模板管理</Link>
        <Link to="/tasks">任务记录</Link>
        <Link to="/preview">预览下载</Link>
        <Link to="/settings">系统配置</Link>
      </nav>
      <Outlet />
    </div>
  );
}
