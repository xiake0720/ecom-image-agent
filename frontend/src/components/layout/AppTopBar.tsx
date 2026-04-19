import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { V1_TOP_NAV_ITEMS } from "../../config/v1Scope";
import { useAuth } from "../../hooks/useAuth";

interface AppTopBarProps {
  activeKey: string;
  rightSlot?: ReactNode;
}

/** 统一顶部栏：仅暴露一期冻结后的工作台入口，并显示当前登录用户。 */
export function AppTopBar({ activeKey, rightSlot }: AppTopBarProps) {
  const { user, logout } = useAuth();
  const displayName = user?.nickname || user?.email || "未登录";
  const avatarText = buildAvatarText(displayName);

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
        <span className="status-pill">V1</span>
        <span className="topbar-user" title={user?.email}>
          {displayName}
        </span>
        <button type="button" className="topbar-logout-btn" onClick={() => void logout()}>
          退出
        </button>
        <span className="avatar">{avatarText}</span>
        {rightSlot}
      </div>
    </header>
  );
}

function buildAvatarText(label: string): string {
  const trimmed = label.trim();
  if (!trimmed) {
    return "AI";
  }
  return trimmed.slice(0, 2).toUpperCase();
}
