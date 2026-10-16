export const AREA_LABEL: Record<string, string> = {
  LC: "Linguagens",
  CH: "Ciências Humanas",
  CN: "Ciências da Natureza",
  MT: "Matemática",
  CP: "Concursos",
};

export const ENEM_AREAS = ["LC", "CH", "CN", "MT"];
export const LEVEL_LABEL: Record<string, string> = { medio: "Nível médio", superior: "Nível superior" };
export const FORMAT_LABEL: Record<string, string> = {
  multiple_choice: "Múltipla escolha",
  true_false: "Certo ou errado",
};

export const DIFFICULTY_LABEL: Record<string, string> = {
  facil: "Fácil",
  media: "Média",
  dificil: "Difícil",
};

export const LANGUAGE_LABEL: Record<string, string> = { ingles: "Inglês", espanhol: "Espanhol" };

export const YEARS = Array.from({ length: 2023 - 2009 + 1 }, (_, i) => 2023 - i);

/** Filtros da tela ⇄ query string (?area=MT&year=2023...). */
export type FilterState = {
  track?: string;
  area?: string;
  subject_id?: string;
  topic_id?: string;
  year?: string;
  difficulty?: string;
  language?: string;
  status?: string;
  q?: string;
  board?: string;
  organization?: string;
  position?: string;
  level?: string;
  format?: string;
};

export const FILTER_KEYS: (keyof FilterState)[] = [
  "track",
  "area",
  "subject_id",
  "topic_id",
  "year",
  "difficulty",
  "language",
  "status",
  "q",
  "board",
  "organization",
  "position",
  "level",
  "format",
];

export function filtersFromParams(params: URLSearchParams): FilterState {
  const out: FilterState = {};
  for (const k of FILTER_KEYS) {
    const v = params.get(k);
    if (v) out[k] = v;
  }
  return out;
}

/** Converte para o formato da API (números onde precisa). */
export function toApiFilters(f: FilterState) {
  return {
    track: (f.track === "concurso" ? "concurso" : "enem") as "enem" | "concurso",
    board: f.board || undefined,
    organization: f.organization || undefined,
    position: f.position || undefined,
    level: (f.level || undefined) as "medio" | "superior" | undefined,
    format: (f.format || undefined) as "multiple_choice" | "true_false" | undefined,
    area: f.area || undefined,
    subject_id: f.subject_id ? Number(f.subject_id) : undefined,
    topic_id: f.topic_id ? Number(f.topic_id) : undefined,
    year: f.year ? Number(f.year) : undefined,
    difficulty: (f.difficulty || undefined) as "facil" | "media" | "dificil" | undefined,
    language: (f.language || undefined) as "ingles" | "espanhol" | undefined,
    status: (f.status || undefined) as "nao_respondidas" | "erradas" | "favoritas" | undefined,
    q: f.q || undefined,
  };
}
