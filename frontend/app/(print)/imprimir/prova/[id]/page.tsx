import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { AssessmentPrint } from "./assessment-print";

export const metadata: Metadata = { title: "Prova para imprimir" };

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <AssessmentPrint />
    </Suspense>
  );
}
