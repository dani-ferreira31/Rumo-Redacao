"use client";

import { Alert } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export function RequireTeacher({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (user?.role !== "teacher" && user?.role !== "admin") {
    return <Alert>Área restrita a professores.</Alert>;
  }
  return <>{children}</>;
}
