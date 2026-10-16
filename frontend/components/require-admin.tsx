"use client";

import { Alert } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (user?.role !== "admin") return <Alert>Área restrita a administradores.</Alert>;
  return <>{children}</>;
}
