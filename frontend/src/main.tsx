import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { DetailPageGeneratorPage } from "./pages/DetailPageGeneratorPage";
import { LoginPage } from "./pages/LoginPage";
import { MainImagePage } from "./pages/MainImagePage";
import { PreviewPage } from "./pages/PreviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TasksPage } from "./pages/TasksPage";
import { TemplatesPage } from "./pages/TemplatesPage";

/**
 * React 入口。
 * 路由策略：默认首页直接进入主图生成工作台，符合当前产品主路径。
 */
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/main-images" replace />} />
          <Route path="main-images" element={<MainImagePage />} />
          <Route path="detail-pages" element={<DetailPageGeneratorPage />} />
          <Route path="templates" element={<TemplatesPage />} />
          <Route path="tasks" element={<TasksPage />} />
          <Route path="preview" element={<PreviewPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/main-images" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
