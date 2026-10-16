import type { Metadata } from "next";

import { QuestionStatsView } from "./stats-view";

export const metadata: Metadata = { title: "Estatísticas" };

export default function Page() {
  return <QuestionStatsView />;
}
