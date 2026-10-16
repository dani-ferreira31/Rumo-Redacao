import type { components } from "@/lib/api-schema";

type S = components["schemas"];
export type AssessmentSummary = S["AssessmentSummary"];
export type AssessmentDetail = S["AssessmentDetail"];
export type TeacherQuestion = S["TeacherQuestion"];
export type AssessmentResults = S["AssessmentResults"];
export type AssessmentPublic = S["AssessmentPublic"];
export type Attempt = S["AttemptOut"];
export type Letter = "A" | "B" | "C" | "D" | "E";

export function pct(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : `${value.toLocaleString("pt-BR")}%`;
}

/** Alternativas a mostrar: Certo/Errado vira C e E. */
export function optionsOf(q: { format?: string; options: { letter: string; text_md: string }[] }) {
  return q.format === "true_false"
    ? [
        { letter: "C", text_md: "**Certo**" },
        { letter: "E", text_md: "**Errado**" },
      ]
    : q.options;
}
