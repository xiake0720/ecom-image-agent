import axios from "axios";

/**
 * API 客户端。
 * 输入：环境变量中配置的后端地址。
 * 输出：统一的 axios 实例，后续可扩展鉴权拦截器。
 */
export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api",
  timeout: 60000,
});
