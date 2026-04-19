import axios from "axios";
import { getAccessToken } from "./authToken";

/**
 * API 客户端。
 * 输入：环境变量中配置的后端地址。
 * 输出：统一的 axios 实例与静态资源 URL 解析工具。
 */
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";

export const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  withCredentials: true,
});

http.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * 把后端返回的 `/api/...` 相对路径解析成当前浏览器可直接访问的绝对地址。
 */
export function resolveApiUrl(path: string): string {
  if (!path) {
    return "";
  }
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return new URL(path, `${API_BASE_URL}/`).toString();
}
