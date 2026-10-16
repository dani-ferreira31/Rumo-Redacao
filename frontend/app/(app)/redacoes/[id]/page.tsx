import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { EssayDetail } from "./essay-detail";

export const metadata: Metadata = { title: "Redação" };

export default function EssayPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <EssayDetail />
    </Suspense>
  );
}
