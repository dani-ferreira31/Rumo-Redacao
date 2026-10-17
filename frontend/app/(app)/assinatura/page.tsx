import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { SubscriptionPage } from "./subscription-page";

export const metadata: Metadata = { title: "Assinatura" };

export default function Page() {
  return (
    <Suspense fallback={<Spinner />}>
      <SubscriptionPage />
    </Suspense>
  );
}
