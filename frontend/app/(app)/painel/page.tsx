import type { Metadata } from "next";

import { Dashboard } from "./dashboard";

export const metadata: Metadata = { title: "Painel" };

export default function PainelPage() {
  return <Dashboard />;
}
