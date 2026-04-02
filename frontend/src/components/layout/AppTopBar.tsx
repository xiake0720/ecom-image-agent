import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { topNavItems } from "../../mocks/sharedMock";

interface AppTopBarProps {
  activeKey: string;
  rightSlot?: ReactNode;
}

/** 统一顶部任务栏：保证全站导航、状态和用户入口一致。 */
export function AppTopBar({ activeKey, rightSlot }: AppTopBarProps) {
  return (
    <header className="app-topbar">
      <div className="topbar-brand">
        <div className="topbar-logo">E</div>
        <div>
          <strong>ECOM AI</strong>
          <p>电商图片生产工作台</p>
        </div>
      </div>
      <nav className="topbar-nav" aria-label="主导航">
        {topNavItems.map((item) => (
          <Link key={item.key} to={item.path} className={activeKey === item.key ? "active" : ""}>
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="topbar-actions">
        <span className="status-pill">任务队列 2</span>
        <Link to="/dashboard">数据中心</Link>
        <Link to="/assets-library">资源库</Link>
        <Link to="/settings">系统设置</Link>
        <span className="avatar">AI</span>
        {rightSlot}
      </div>
    </header>
  );
}
