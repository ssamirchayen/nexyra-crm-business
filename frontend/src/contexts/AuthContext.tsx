import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  api,
  AUTH_UNAUTHORIZED_EVENT,
  clearAccessToken,
  getAccessToken,
  storeAccessToken,
} from "../lib/api";
import type {
  AuthContextPayload,
  AuthLoginResponse,
  AuthMessageResponse,
  AuthPasswordRecoveryRequestedResponse,
  AuthUser,
  AuthWorkspace,
} from "../types/auth";

type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  workspaces: AuthWorkspace[];
  notice: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  refreshSession: () => Promise<void>;
  requestPasswordRecovery: (email: string) => Promise<AuthPasswordRecoveryRequestedResponse>;
  resetPassword: (token: string, newPassword: string) => Promise<string>;
  clearNotice: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [context, setContext] = useState<AuthContextPayload | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const becomeAnonymous = useCallback((message?: string) => {
    clearAccessToken();
    setContext(null);
    setStatus("anonymous");
    if (message) {
      setNotice(message);
    }
  }, []);

  const refreshSession = useCallback(async () => {
    if (!getAccessToken()) {
      becomeAnonymous();
      return;
    }

    try {
      const payload = await api.get<AuthContextPayload>("/auth/me");
      setContext(payload);
      setStatus("authenticated");
    } catch (error) {
      if (!getAccessToken()) {
        becomeAnonymous("Sua sessão expirou ou foi encerrada. Entre novamente.");
        return;
      }

      becomeAnonymous(
        error instanceof Error
          ? `Não foi possível validar sua sessão: ${error.message}`
          : "Não foi possível validar sua sessão.",
      );
    }
  }, [becomeAnonymous]);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  useEffect(() => {
    const handleUnauthorized = (event: Event) => {
      const customEvent = event as CustomEvent<{ message?: string }>;
      becomeAnonymous(
        customEvent.detail?.message
          ? `Sessão encerrada: ${customEvent.detail.message}`
          : "Sua sessão expirou ou foi encerrada. Entre novamente.",
      );
    };

    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
  }, [becomeAnonymous]);

  const login = useCallback(async (email: string, password: string) => {
    const payload = await api.post<AuthLoginResponse>("/auth/login", {
      email,
      password,
    });

    storeAccessToken(payload.access_token);
    setContext({ user: payload.user, workspaces: payload.workspaces });
    setNotice(null);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      if (getAccessToken()) {
        await api.post<AuthMessageResponse>("/auth/logout");
      }
    } finally {
      clearAccessToken();
      setContext(null);
      setNotice(null);
      setStatus("anonymous");
    }
  }, []);

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      const response = await api.post<AuthMessageResponse>("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      becomeAnonymous(response.message);
    },
    [becomeAnonymous],
  );

  const requestPasswordRecovery = useCallback(async (email: string) => {
    return api.post<AuthPasswordRecoveryRequestedResponse>(
      "/auth/password-recovery/request",
      { email },
    );
  }, []);

  const resetPassword = useCallback(
    async (token: string, newPassword: string) => {
      const response = await api.post<AuthMessageResponse>(
        "/auth/password-recovery/reset",
        { token, new_password: newPassword },
      );
      becomeAnonymous(response.message);
      return response.message;
    },
    [becomeAnonymous],
  );

  const clearNotice = useCallback(() => setNotice(null), []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: context?.user ?? null,
      workspaces: context?.workspaces ?? [],
      notice,
      login,
      logout,
      changePassword,
      refreshSession,
      requestPasswordRecovery,
      resetPassword,
      clearNotice,
    }),
    [
      changePassword,
      clearNotice,
      context,
      login,
      logout,
      notice,
      refreshSession,
      requestPasswordRecovery,
      resetPassword,
      status,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);

  if (!value) {
    throw new Error("useAuth precisa ser usado dentro de AuthProvider.");
  }

  return value;
}
