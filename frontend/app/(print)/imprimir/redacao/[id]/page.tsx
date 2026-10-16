import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { EssayReport } from "./essay-report";

export const metadata: Metadata = { title: "Devolutiva da redação" };

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <EssayReport />
    </Suspense>
  );
}
