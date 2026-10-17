import type { Metadata } from "next";

import { LogsAdmin } from "./logs-admin";

export const metadata: Metadata = { title: "Admin · Logs" };

export default function LogsPage() {
  return <LogsAdmin />;
}
