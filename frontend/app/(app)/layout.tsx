import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { RequireAuth } from "@/components/require-auth";
import { Spinner } from "@/components/ui";
import { VerifyEmailBanner } from "@/components/verify-email-banner";
import { FeaturesProvider } from "@/lib/features";

// A área logada é protegida no cliente (o token fica só em memória), então o
// servidor não tem como pré-renderizar o conteúdo: o segmento pode bloquear.
export const instant = false;

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Spinner />
        </div>
      }
    >
      <RequireAuth>
        <FeaturesProvider>
          <AppShell>
            <VerifyEmailBanner />
            {children}
          </AppShell>
        </FeaturesProvider>
      </RequireAuth>
    </Suspense>
  );
}
