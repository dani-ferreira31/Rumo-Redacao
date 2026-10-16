import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { QuestionEditor } from "./question-editor";

export const metadata: Metadata = { title: "Editar questão" };

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <QuestionEditor />
    </Suspense>
  );
}
