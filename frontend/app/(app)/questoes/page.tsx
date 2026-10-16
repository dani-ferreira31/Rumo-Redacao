import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { QuestionsBrowser } from "./questions-browser";

export const metadata: Metadata = { title: "Questões" };

export default function QuestionsPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <QuestionsBrowser />
    </Suspense>
  );
}
