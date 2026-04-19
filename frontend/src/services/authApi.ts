import { http } from "./http";
import type { ApiEnvelope } from "../types/api";
import type { AuthTokenResponse, LoginPayload, RegisterPayload, UserProfile } from "../types/auth";

export async function login(payload: LoginPayload): Promise<AuthTokenResponse> {
  const resp = await http.post<ApiEnvelope<AuthTokenResponse>>("/v1/auth/login", payload);
  return resp.data.data;
}

export async function register(payload: RegisterPayload): Promise<AuthTokenResponse> {
  const resp = await http.post<ApiEnvelope<AuthTokenResponse>>("/v1/auth/register", payload);
  return resp.data.data;
}

export async function refreshAuth(): Promise<AuthTokenResponse> {
  const resp = await http.post<ApiEnvelope<AuthTokenResponse>>("/v1/auth/refresh");
  return resp.data.data;
}

export async function logout(): Promise<void> {
  await http.post<ApiEnvelope<{ logged_out: boolean }>>("/v1/auth/logout");
}

export async function fetchCurrentUser(): Promise<UserProfile> {
  const resp = await http.get<ApiEnvelope<UserProfile>>("/v1/auth/me");
  return resp.data.data;
}
