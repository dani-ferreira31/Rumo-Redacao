import type { Metadata } from "next";

import { Planner } from "./planner";

export const metadata: Metadata = { title: "Cronograma" };

export default function CronogramaPage() {
  return <Planner />;
}
