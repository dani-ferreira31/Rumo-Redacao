import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { ReviewQueue } from "./review-queue";

export const metadata: Metadata = { title: "Revisão de questões" };

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <ReviewQueue />
    </Suspense>
  );
}
