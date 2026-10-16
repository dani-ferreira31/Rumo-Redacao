import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { PracticeRunner } from "./practice-runner";

export const metadata: Metadata = { title: "Prática" };

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <PracticeRunner />
    </Suspense>
  );
}
