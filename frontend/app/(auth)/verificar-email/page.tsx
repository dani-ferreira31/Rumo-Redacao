import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { VerifyEmail } from "./verify-email";

export const metadata: Metadata = { title: "Confirmar e-mail" };

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <VerifyEmail />
    </Suspense>
  );
}
