import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { EditAssessment } from "./edit-assessment";

export const metadata: Metadata = { title: "Editar prova" };

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <EditAssessment />
    </Suspense>
  );
}
