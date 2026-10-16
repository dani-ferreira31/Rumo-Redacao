import createClient from "openapi-fetch";

import type { components, paths } from "@/lib/api-schema";

export type User = components["schemas"]["UserOut"];
export type TokenOut = components["schemas"]["TokenOut"];
export type Essay = components["schemas"]["EssayOut"];
export type EssaySummary = components["schemas"]["EssaySummary"];
export type EssayResult = components["schemas"]["ResultOut"];
export type EssayStats = components["schemas"]["StatsOut"];
export type Theme = components["schemas"]["ThemeOut"];
export type Area = components["schemas"]["AreaOut"];
export type QuestionItem = components["schemas"]["QuestionListItem"];
export type Question = components["schemas"]["QuestionOut"];
export type AdminQuestion = components["schemas"]["AdminQuestionOut"];
export type AnswerResult = components["schemas"]["AnswerOut"];
export type PracticeSession = components["schemas"]["PracticeSessionOut"];
export type SessionResult = components["schemas"]["SessionResult"];
export type QuestionStats = components["schemas"]["QuestionStatsOut"];
export type QuestionFilters = components["schemas"]["QuestionFilters"];
export type StudyPlan = components["schemas"]["PlanOut"];
export type StudyPlanItem = components["schemas"]["PlanListItem"];
export type StudyBlock = components["schemas"]["BlockOut"];
export type PlanSummary = components["schemas"]["PlanSummary"];

/** Formato padrão de erro da API (docs/04-api.md). */
export type ApiError = {
  error: {
    code: string;
    message: string;
    details: { fields?: { field: string; message: string }[] } & Record<string, unknown>;
  };
};

// ---- access token em memória (nunca em localStorage) ------------------------

let accessToken: string | null = null;
let onSessionExpired: (() => void) | null = null;
let refreshInFlight: Promise<string | null> | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setSessionExpiredHandler(handler: (() => void) | null) {
  onSessionExpired = handler;
}

/**
 * Renova o access token usando o cookie httpOnly de refresh.
 * Chamadas simultâneas compartilham a mesma requisição.
 */
export function refreshAccessToken(): Promise<string | null> {
  refreshInFlight ??= (async () => {
    try {
      const res = await fetch("/api/v1/auth/refresh", { method: "POST", credentials: "include" });
      if (!res.ok) return null;
      const body = (await res.json()) as TokenOut;
      accessToken = body.access_token;
      return accessToken;
    } catch {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

function withAuth(request: Request): Request {
  if (accessToken) request.headers.set("Authorization", `Bearer ${accessToken}`);
  return request;
}

/** fetch que injeta o Bearer e, se receber 401, renova a sessão e tenta 1 vez de novo. */
async function authFetch(input: Request): Promise<Response> {
  const retry = input.clone();
  const res = await fetch(withAuth(input));
  if (res.status !== 401 || new URL(input.url).pathname.startsWith("/api/v1/auth/")) {
    return res;
  }
  const token = await refreshAccessToken();
  if (!token) {
    onSessionExpired?.();
    return res;
  }
  return fetch(withAuth(retry));
}

/** fetch autenticado para casos fora do cliente tipado (ex.: upload multipart). */
export function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return authFetch(new Request(path, { credentials: "include", ...init }));
}

// Mesma origem: em dev o Next faz rewrite de /api/v1 para o backend; em produção, o Nginx Proxy Manager.
export const api = createClient<paths>({
  baseUrl: typeof window === "undefined" ? "http://localhost" : window.location.origin,
  credentials: "include",
  fetch: authFetch,
});

export function isApiError(err: unknown): err is ApiError {
  return Boolean(err && typeof err === "object" && "error" in err);
}

export function errorMessage(err: unknown, fallback = "Algo deu errado. Tente novamente.") {
  return (isApiError(err) && err.error?.message) || fallback;
}

export function errorCode(err: unknown): string | null {
  return isApiError(err) ? err.error.code : null;
}

/** Erros de validação (422) por campo: { campo: mensagem }. */
export function fieldErrors(err: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (isApiError(err)) {
    for (const f of err.error.details?.fields ?? []) {
      out[f.field] ??= f.message.replace(/^Value error, /, "");
    }
  }
  return out;
}
