const ACCESS_TOKEN_KEY = "ecom-access-token";

/** 读取前端持有的 access token。 */
export function getAccessToken(): string {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY) ?? "";
}

/** 保存 access token，供统一 HTTP 拦截器注入。 */
export function setAccessToken(token: string): void {
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

/** 清理 access token，登出或 refresh 失败时调用。 */
export function clearAccessToken(): void {
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
}
