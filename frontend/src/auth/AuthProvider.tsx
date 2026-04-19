import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  fetchCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  refreshAuth,
  register as registerRequest,
} from "../services/authApi";
import { clearAccessToken, getAccessToken, setAccessToken } from "../services/authToken";
import type { AuthTokenResponse, LoginPayload, RegisterPayload, UserProfile } from "../types/auth";

type AuthStatus = "bootstrapping" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: UserProfile | null;
  status: AuthStatus;
  isAuthenticated: boolean;
  login: (payload: LoginPayload) => Promise<UserProfile>;
  register: (payload: RegisterPayload) => Promise<UserProfile>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<UserProfile | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

/** 统一维护前端登录态，避免页面直接读写 token。 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [status, setStatus] = useState<AuthStatus>("bootstrapping");

  const applyAuthResult = useCallback((result: AuthTokenResponse): UserProfile => {
    setAccessToken(result.access_token);
    setUser(result.user);
    setStatus("authenticated");
    return result.user;
  }, []);

  const refreshSession = useCallback(async (): Promise<UserProfile | null> => {
    try {
      const result = await refreshAuth();
      return applyAuthResult(result);
    } catch {
      clearAccessToken();
      setUser(null);
      setStatus("anonymous");
      return null;
    }
  }, [applyAuthResult]);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const token = getAccessToken();
        if (token) {
          try {
            const profile = await fetchCurrentUser();
            if (!cancelled) {
              setUser(profile);
              setStatus("authenticated");
            }
            return;
          } catch {
            const result = await refreshAuth();
            if (!cancelled) {
              applyAuthResult(result);
            }
            return;
          }
        }

        const result = await refreshAuth();
        if (!cancelled) {
          applyAuthResult(result);
        }
      } catch {
        if (!cancelled) {
          clearAccessToken();
          setUser(null);
          setStatus("anonymous");
        }
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [applyAuthResult]);

  const login = useCallback(
    async (payload: LoginPayload): Promise<UserProfile> => {
      const result = await loginRequest(payload);
      return applyAuthResult(result);
    },
    [applyAuthResult],
  );

  const register = useCallback(
    async (payload: RegisterPayload): Promise<UserProfile> => {
      const result = await registerRequest(payload);
      return applyAuthResult(result);
    },
    [applyAuthResult],
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await logoutRequest();
    } finally {
      clearAccessToken();
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      isAuthenticated: status === "authenticated",
      login,
      register,
      logout,
      refreshSession,
    }),
    [login, logout, refreshSession, register, status, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
