import type { Essay } from "@/lib/api";

export const ESSAY_STATUS_LABEL: Record<Essay["status"], string> = {
  uploaded: "Enviada",
  transcribing: "Transcrevendo",
  awaiting_review: "Aguardando sua revisão",
  grading: "Corrigindo",
  graded: "Corrigida",
  failed: "Falhou",
};

export const ESSAY_STATUS_STYLE: Record<Essay["status"], string> = {
  uploaded: "bg-slate-100 text-slate-700",
  transcribing: "bg-sky-100 text-sky-800",
  awaiting_review: "bg-amber-100 text-amber-900",
  grading: "bg-sky-100 text-sky-800",
  graded: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

/** Estados em que o worker está trabalhando: a tela consulta de novo a cada 3 s. */
export const PROCESSING_STATUSES: Essay["status"][] = ["uploaded", "transcribing", "grading"];

export const COMPETENCY_NAMES: Record<number, string> = {
  1: "Domínio da escrita formal",
  2: "Compreensão da proposta e repertório",
  3: "Organização dos argumentos",
  4: "Coesão",
  5: "Proposta de intervenção",
};

export const ZERO_REASON_LABEL: Record<string, string> = {
  folha_em_branco: "Folha em branco",
  texto_insuficiente: "Texto insuficiente (até 7 linhas)",
  fuga_total_ao_tema: "Fuga total ao tema",
  nao_dissertativo_argumentativo: "Não atende ao tipo dissertativo-argumentativo",
  parte_desconectada: "Parte deliberadamente desconectada do tema",
  copia_textos_motivadores: "Cópia dos textos motivadores",
  lingua_estrangeira: "Texto em língua estrangeira",
  identificacao: "Identificação do participante",
  improperios_ou_anulacao: "Impropérios ou outra forma de anulação",
  ilegivel: "Texto ilegível",
};

export const C5_ELEMENT_LABEL: Record<string, string> = {
  agente: "Agente (quem)",
  acao: "Ação (o quê)",
  meio: "Meio/modo (como)",
  finalidade: "Finalidade (para quê)",
  detalhamento: "Detalhamento",
};

export const DEVIATION_LABEL: Record<string, string> = {
  ortografia: "Ortografia",
  acentuacao: "Acentuação",
  pontuacao: "Pontuação",
  concordancia: "Concordância",
  regencia: "Regência",
  crase: "Crase",
  sintaxe: "Sintaxe",
  vocabulario: "Vocabulário",
  registro: "Registro informal",
  outro: "Outro",
};

export const MARKER_RE = /\[ilegível\]|\[\?[^\]]*\]/g;

export function findMarkers(text: string): { line: number; marker: string }[] {
  const out: { line: number; marker: string }[] = [];
  text.split("\n").forEach((line, i) => {
    for (const m of line.matchAll(MARKER_RE)) out.push({ line: i + 1, marker: m[0] });
  });
  return out;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}
