import type { ReactNode } from "react";
import { AppTopBar } from "./AppTopBar";

interface PageShellProps {
  activeKey: string;
  children: ReactNode;
}

/** 页面壳层：统一背景、顶部栏和主内容宽度。 */
export function PageShell({ activeKey, children }: PageShellProps) {
  return (
    <div className="console-shell">
      <AppTopBar activeKey={activeKey} />
      <main className="console-main">{children}</main>
    </div>
  );
}
