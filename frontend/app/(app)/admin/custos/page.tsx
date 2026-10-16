import type { Metadata } from "next";

import { CostsDashboard } from "./costs";

export const metadata: Metadata = { title: "Admin · Custos" };

export default function CostsPage() {
  return <CostsDashboard />;
}
