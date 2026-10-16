import type { Metadata } from "next";

import { NewEssayForm } from "./new-essay-form";

export const metadata: Metadata = { title: "Nova redação" };

export default function NewEssayPage() {
  return <NewEssayForm />;
}
