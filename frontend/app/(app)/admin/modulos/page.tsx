import type { Metadata } from "next";

import { ModulesPanel } from "./modules";

export const metadata: Metadata = { title: "Admin · Módulos e limites" };

export default function ModulesPage() {
  return <ModulesPanel />;
}
