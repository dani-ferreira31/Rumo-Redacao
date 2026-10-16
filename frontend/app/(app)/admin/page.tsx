import type { Metadata } from "next";

import { AdminOverview } from "./overview";

export const metadata: Metadata = { title: "Admin · Visão geral" };

export default function AdminPage() {
  return <AdminOverview />;
}
