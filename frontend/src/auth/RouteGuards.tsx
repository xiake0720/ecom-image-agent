import { Navigate, useLocation } from "react-router-dom";
import { DEFAULT_V1_WORKSPACE_ROUTE } from "../config/v1Scope";
import { useAuth } from "../hooks/useAuth";
import type { ReactNode } from "react";

interface RouteGuardProps {
  children: ReactNode;
}

/** 保护工作台路由，未登录时跳转登录页。 */
export function RequireAuth({ children }: RouteGuardProps) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "bootstrapping") {
    return <AuthLoadingScreen />;
  }

  if (status !== "authenticated") {
    const redirect = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?redirect=${encodeURIComponent(redirect)}`} replace />;
  }

  return <>{children}</>;
}

/** 登录后访问登录/注册页时直接回工作台。 */
export function PublicOnly({ children }: RouteGuardProps) {
  const { status } = useAuth();

  if (status === "bootstrapping") {
    return <AuthLoadingScreen />;
  }

  if (status === "authenticated") {
    return <Navigate to={DEFAULT_V1_WORKSPACE_ROUTE} replace />;
  }

  return <>{children}</>;
}

function AuthLoadingScreen() {
  return (
    <div className="console-shell login-shell">
      <div className="section-card login-card">
        <h2>正在恢复登录态</h2>
        <p>系统正在校验本地 access token 或 refresh cookie。</p>
      </div>
    </div>
  );
}
