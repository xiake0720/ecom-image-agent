import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthProvider";
import { PublicOnly, RequireAuth } from "./auth/RouteGuards";
import { Layout } from "./components/Layout";
import {
  DEFAULT_V1_WORKSPACE_ROUTE,
  isRouteEnabled,
  type AppRouteKey,
} from "./config/v1Scope";
import { AssetsLibraryPage } from "./pages/AssetsLibraryPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DetailPageGeneratorPage } from "./pages/DetailPageGeneratorPage";
import { LoginPage } from "./pages/LoginPage";
import { MainImagePage } from "./pages/MainImagePage";
import { PreviewPage } from "./pages/PreviewPage";
import { RegisterPage } from "./pages/RegisterPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TasksPage } from "./pages/TasksPage";
import { TemplatesPage } from "./pages/TemplatesPage";
import "./pages/WorkbenchRefine.css";
import "./styles/console.css";

interface WorkspaceRouteDefinition {
  key: AppRouteKey;
  path: string;
  element: React.ReactElement;
}

const workspaceRoutes: WorkspaceRouteDefinition[] = [
  { key: "dashboard", path: "dashboard", element: <DashboardPage /> },
  { key: "main-images", path: "main-images", element: <MainImagePage /> },
  { key: "detail-pages", path: "detail-pages", element: <DetailPageGeneratorPage /> },
  { key: "templates", path: "templates", element: <TemplatesPage /> },
  { key: "tasks", path: "tasks", element: <TasksPage /> },
  { key: "preview", path: "preview", element: <PreviewPage /> },
  { key: "settings", path: "settings", element: <SettingsPage /> },
  { key: "assets-library", path: "assets-library", element: <AssetsLibraryPage /> },
];

/**
 * React 入口。
 * 为什么这样处理：工作台路由统一要求登录，非一期页面仍保留代码但不暴露入口。
 */
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={
              isRouteEnabled("login") ? (
                <PublicOnly>
                  <LoginPage />
                </PublicOnly>
              ) : (
                <Navigate to={DEFAULT_V1_WORKSPACE_ROUTE} replace />
              )
            }
          />
          <Route
            path="/register"
            element={
              isRouteEnabled("register") ? (
                <PublicOnly>
                  <RegisterPage />
                </PublicOnly>
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />
          <Route
            path="/"
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to={DEFAULT_V1_WORKSPACE_ROUTE} replace />} />
            {workspaceRoutes.map((route) => (
              <Route
                key={route.path}
                path={route.path}
                element={isRouteEnabled(route.key) ? route.element : <Navigate to={DEFAULT_V1_WORKSPACE_ROUTE} replace />}
              />
            ))}
          </Route>
          <Route path="*" element={<Navigate to={DEFAULT_V1_WORKSPACE_ROUTE} replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>,
);
