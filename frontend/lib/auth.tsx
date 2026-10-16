"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  api,
  refreshAccessToken,
  setAccessToken,
  setSessionExpiredHandler,
  type TokenOut,
  type User,
} from "@/lib/api";

type Status = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  status: Status;
  user: User | null;
  /** Guarda o token recebido no login/cadastro e carrega o perfil. */
  startSession: (tokens: TokenOut) => Promise<void>;
  reloadUser: () => Promise<void>;
  setUser: (user: User) => void;
  logout: () => Promise<void>;
  /** Limpa a sessão local sem chamar a API (ex.: após excluir a conta). */
  clearSession: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUserState] = useState<User | null>(null);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUserState(null);
    setStatus("anonymous");
  }, []);

  const reloadUser = useCallback(async () => {
    const { data } = await api.GET("/api/v1/me");
    if (data) {
      setUserState(data);
      setStatus("authenticated");
    } else {
      clearSession();
    }
  }, [clearSession]);

  const startSession = useCallback(
    async (tokens: TokenOut) => {
      setAccessToken(tokens.access_token);
      await reloadUser();
    },
    [reloadUser],
  );

  const logout = useCallback(async () => {
    await api.POST("/api/v1/auth/logout");
    clearSession();
    router.replace("/entrar");
  }, [clearSession, router]);

  // Restaura a sessão a partir do cookie de refresh ao abrir o app.
  useEffect(() => {
    let cancelled = false;
    setSessionExpiredHandler(() => {
      if (!cancelled) clearSession();
    });
    refreshAccessToken().then(async (token) => {
      if (cancelled) return;
      if (token) await reloadUser();
      else clearSession();
    });
    return () => {
      cancelled = true;
      setSessionExpiredHandler(null);
    };
  }, [clearSession, reloadUser]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      startSession,
      reloadUser,
      setUser: setUserState,
      logout,
      clearSession,
    }),
    [status, user, startSession, reloadUser, logout, clearSession],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth precisa estar dentro de <AuthProvider>");
  return ctx;
}
