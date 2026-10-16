import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { ContestReview } from "./contest-review";

export const metadata: Metadata = { title: "Admin · Revisão da prova" };

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <ContestReview />
    </Suspense>
  );
}
