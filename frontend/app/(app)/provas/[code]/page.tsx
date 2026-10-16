import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { AssessmentTaker } from "./assessment-taker";

export const metadata: Metadata = { title: "Prova" };

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <AssessmentTaker />
    </Suspense>
  );
}
