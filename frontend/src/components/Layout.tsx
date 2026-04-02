import { Outlet } from "react-router-dom";

/** 路由布局容器：页面自身负责渲染统一壳层。 */
export function Layout() {
  return <Outlet />;
}
