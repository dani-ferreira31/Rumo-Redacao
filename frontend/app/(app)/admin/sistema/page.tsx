import type { Metadata } from "next";

import { SystemPanel } from "./system";

export const metadata: Metadata = { title: "Admin · Sistema" };

export default function SystemPage() {
  return <SystemPanel />;
}
