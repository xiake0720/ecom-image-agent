import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { V1_TOP_NAV_ITEMS } from "../../config/v1Scope";

interface AppTopBarProps {
  activeKey: string;
  rightSlot?: ReactNode;
}

/** 统一顶部栏：仅暴露一期冻结后的工作台入口。 */
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
        {V1_TOP_NAV_ITEMS.map((item) => (
          <Link key={item.key} to={item.path} className={activeKey === item.key ? "active" : ""}>
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="topbar-actions">
        <span className="status-pill">V1 Freeze</span>
        <Link to="/login">账号入口</Link>
        <span className="avatar">AI</span>
        {rightSlot}
      </div>
    </header>
  );
}
