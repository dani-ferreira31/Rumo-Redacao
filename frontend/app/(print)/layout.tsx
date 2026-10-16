import { Suspense } from "react";

import { RequireAuth } from "@/components/require-auth";
import { Spinner } from "@/components/ui";

// Páginas para imprimir ou salvar em PDF: sem menu lateral, mesma proteção da área logada.
export const instant = false;

export default function PrintLayout({ children }: LayoutProps<"/">) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Spinner />
        </div>
      }
    >
      <RequireAuth>
        <div className="min-h-screen bg-white print:min-h-0">{children}</div>
      </RequireAuth>
    </Suspense>
  );
}
