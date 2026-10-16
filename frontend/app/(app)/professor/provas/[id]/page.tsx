import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { AssessmentManage } from "./assessment-manage";

export const metadata: Metadata = { title: "Prova" };

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <AssessmentManage />
    </Suspense>
  );
}
