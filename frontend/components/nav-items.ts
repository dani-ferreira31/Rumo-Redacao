export const NAV_ITEMS = [
  { href: "/painel", label: "Painel", features: [] },
  { href: "/redacoes", label: "Redações", features: ["essays"] },
  { href: "/questoes", label: "Questões", features: ["questions_enem", "questions_concursos"] },
  { href: "/cronograma", label: "Cronograma", features: ["planner"] },
] as const;
