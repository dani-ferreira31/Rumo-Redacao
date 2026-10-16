import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { QuestionPage } from "./question-page";

export const metadata: Metadata = { title: "Questão" };

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <QuestionPage />
    </Suspense>
  );
}
