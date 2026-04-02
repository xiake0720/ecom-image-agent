import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { AssetsLibraryPage } from "./pages/AssetsLibraryPage";
import { DetailPageGeneratorPage } from "./pages/DetailPageGeneratorPage";
import { LoginPage } from "./pages/LoginPage";
import { MainImagePage } from "./pages/MainImagePage";
import { PreviewPage } from "./pages/PreviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TasksPage } from "./pages/TasksPage";
import { TemplatesPage } from "./pages/TemplatesPage";
import "./styles/console.css";
import "./pages/WorkbenchRefine.css";

/**
 * React 入口。
 * 为什么这样分层：通过路由聚合页面，业务组件独立维护，便于持续扩展。
 */
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="main-images" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="main-images" element={<MainImagePage />} />
          <Route path="detail-pages" element={<DetailPageGeneratorPage />} />
          <Route path="templates" element={<TemplatesPage />} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="preview" element={<PreviewPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="assets-library" element={<AssetsLibraryPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/main-images" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
