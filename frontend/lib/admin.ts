import type { components } from "@/lib/api-schema";

type S = components["schemas"];
export type Overview = S["OverviewOut"];
export type Budget = S["Budget"];
export type HealthReport = S["HealthOut"];
export type JobsReport = S["JobsOut"];
export type Job = S["JobOut"];
export type Feature = S["FeatureOut"];
export type Limits = S["Limits"];
export type SystemEvent = S["EventOut"];
export type CostReport = S["CostReport"];
export type Period = CostReport["period"];
export type Provider = S["ProviderOut"];
export type ProvidersReport = S["ProvidersOut"];
export type AITask = S["TaskOut"];
export type PriceRow = S["PriceRow"];
export type Calibration = S["Calibration"];
export type ModelOption = S["ModelOut"];

/** Tarefas de IA, sempre na mesma ordem e com a mesma cor (a cor segue a tarefa). */
export const PURPOSES = [
  { id: "transcription", label: "Transcrição", color: "#2a78d6" },
  { id: "grading", label: "Correção", color: "#eb6834" },
  { id: "contest_extraction", label: "Importação de provas", color: "#1baf7a" },
  { id: "other", label: "Outros", color: "#eda100" },
] as const;

export function purposeOf(id: string) {
  return PURPOSES.find((p) => p.id === id) ?? PURPOSES[PURPOSES.length - 1];
}

export const PERIODS: { id: Period; label: string }[] = [
  { id: "month", label: "Este mês" },
  { id: "last_month", label: "Mês passado" },
  { id: "7d", label: "7 dias" },
  { id: "30d", label: "30 dias" },
  { id: "90d", label: "90 dias" },
];

const usd = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" });
const usdSmall = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
});
const num = new Intl.NumberFormat("pt-BR");
const compact = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });

export function money(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return value !== 0 && Math.abs(value) < 0.01 ? usdSmall.format(value) : usd.format(value);
}

export const fmtInt = (n: number) => num.format(n);
export const fmtCompact = (n: number) => compact.format(n);

export function relativeTime(iso: string | null | undefined) {
  if (!iso) return "nunca";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "agora há pouco";
  if (diff < 3600) return `há ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `há ${Math.floor(diff / 3600)} h`;
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export function dateTime(iso: string) {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export const QUEUE_LABEL: Record<string, string> = {
  "essay.transcribe": "Transcrição de redação",
  "essay.grade": "Correção de redação",
  "email.send": "Envio de e-mail",
  "user.purge_storage": "Limpeza de arquivos",
  "contest.extract": "Importação de prova",
  "system.ping": "Teste (ping)",
};

export const JOB_STATUS_LABEL: Record<string, string> = {
  pending: "Na fila",
  running: "Rodando",
  done: "Concluído",
  failed: "Falhou",
  cancelled: "Cancelado",
};

export type ContestExam = S["ContestExamOut"];
export type ContestExamDetail = S["ContestExamDetail"];
export type ContestQuestion = S["ContestQuestionOut"];
export type ContestEstimate = S["EstimateOut"];

export const CONTEST_STATUS: Record<string, { label: string; level: "ok" | "warning" | "error" }> = {
  processing: { label: "Lendo o PDF", level: "warning" },
  review: { label: "Em revisão", level: "warning" },
  published: { label: "Publicada", level: "ok" },
  failed: { label: "Falhou", level: "error" },
};

export type Invite = S["InviteOut"];
export type AdminUser = S["AdminUserOut"];
export type WelcomeSettings = S["WelcomeSettings"];
export type MessageBody = S["MessageIn"];
export type QuotaUsage = S["QuotaUsage"];
export type QuotaRule = S["QuotaRule"];

export const ROLE_LABEL: Record<string, string> = {
  student: "Aluno",
  teacher: "Professor",
  admin: "Admin",
};

export const INVITE_STATUS: Record<string, { label: string; level: "ok" | "warning" | "error" }> = {
  active: { label: "Ativo", level: "ok" },
  expired: { label: "Vencido", level: "warning" },
  used_up: { label: "Esgotado", level: "warning" },
  revoked: { label: "Revogado", level: "error" },
};
