import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { Unsubscribe } from "./unsubscribe";

export const metadata: Metadata = { title: "Lembretes por e-mail" };

export default function UnsubscribePage() {
  return (
    <Suspense fallback={<Spinner />}>
      <Unsubscribe />
    </Suspense>
  );
}
