import type { Metadata } from "next";
import { Suspense } from "react";

import { Spinner } from "@/components/ui";

import { ResetPasswordForm } from "./reset-password-form";

export const metadata: Metadata = { title: "Nova senha" };

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <ResetPasswordForm />
    </Suspense>
  );
}
