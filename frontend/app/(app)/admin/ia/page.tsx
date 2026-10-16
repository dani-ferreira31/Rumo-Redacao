import type { Metadata } from "next";

import { AIPanel } from "./ai-panel";

export const metadata: Metadata = { title: "Admin · Inteligência artificial" };

export default function AIPage() {
  return <AIPanel />;
}
