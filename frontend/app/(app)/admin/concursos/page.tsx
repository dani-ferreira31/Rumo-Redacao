import type { Metadata } from "next";

import { ContestsAdmin } from "./contests-admin";

export const metadata: Metadata = { title: "Admin · Concursos" };

export default function ContestsPage() {
  return <ContestsAdmin />;
}
