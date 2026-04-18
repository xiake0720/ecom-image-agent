export type AppRouteKey =
  | "login"
  | "register"
  | "main-images"
  | "detail-pages"
  | "tasks"
  | "dashboard"
  | "templates"
  | "preview"
  | "settings"
  | "assets-library";

export interface AppNavItem {
  key: AppRouteKey;
  label: string;
  path: string;
}

/**
 * 一期上线范围冻结开关。
 * 说明：只控制前端入口暴露，不删除既有页面代码，便于后续阶段按需恢复。
 */
export const V1_ROUTE_FLAGS: Record<AppRouteKey, boolean> = {
  login: true,
  register: true,
  "main-images": true,
  "detail-pages": true,
  tasks: true,
  dashboard: false,
  templates: false,
  preview: false,
  settings: false,
  "assets-library": false,
};

export const DEFAULT_V1_WORKSPACE_ROUTE = "/main-images";

export const V1_TOP_NAV_ITEMS: AppNavItem[] = [
  { key: "main-images", label: "主图生成", path: "/main-images" },
  { key: "detail-pages", label: "详情图生成", path: "/detail-pages" },
  { key: "tasks", label: "历史任务", path: "/tasks" },
];

export function isRouteEnabled(key: AppRouteKey): boolean {
  return V1_ROUTE_FLAGS[key];
}
