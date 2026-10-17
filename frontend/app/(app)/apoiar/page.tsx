import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { DonatePage } from "./donate-page";

export const metadata: Metadata = { title: "Apoie o Rumo1000" };

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <DonatePage />
    </Suspense>
  );
}
