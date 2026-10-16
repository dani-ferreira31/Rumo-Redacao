"use client";

import { createContext, useContext, useEffect, useState } from "react";

import { api } from "@/lib/api";

export type Features = Record<string, boolean>;

const FeaturesContext = createContext<Features | null>(null);

/** Módulos ligados no painel admin (`GET /features`). Antes de carregar, tudo ligado. */
export function FeaturesProvider({ children }: { children: React.ReactNode }) {
  const [features, setFeatures] = useState<Features | null>(null);
  useEffect(() => {
    api.GET("/api/v1/features").then(({ data }) => setFeatures(data ?? null));
  }, []);
  return <FeaturesContext.Provider value={features}>{children}</FeaturesContext.Provider>;
}

export function useFeatures(): Features | null {
  return useContext(FeaturesContext);
}

/** Um módulo está ligado se qualquer uma das flags estiver ligada (ex.: questões ENEM ou concursos). */
export function isEnabled(features: Features | null, names: readonly string[] | undefined) {
  if (!features || !names?.length) return true;
  return names.some((n) => features[n] !== false);
}

export const ROUTE_FEATURES: { prefix: string; features: readonly string[]; label: string }[] = [
  { prefix: "/redacoes", features: ["essays"], label: "A correção de redações" },
  { prefix: "/questoes", features: ["questions_enem", "questions_concursos"], label: "O banco de questões" },
  { prefix: "/cronograma", features: ["planner"], label: "O cronograma" },
];
