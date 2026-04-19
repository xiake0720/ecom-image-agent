import axios from "axios";

/** 从 axios / 普通异常中提取前端可展示的错误消息。 */
export function extractApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const payload = error.response?.data as { message?: string; code?: number | string; requestId?: string } | undefined;
    const message = payload?.message || error.message || "请求失败";
    const code = payload?.code ? ` (code: ${payload.code})` : "";
    const requestId = payload?.requestId ? ` [requestId: ${payload.requestId}]` : "";
    return `${message}${code}${requestId}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "未知错误，请稍后重试";
}
