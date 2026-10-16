"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth";

/** Páginas de login/cadastro: quem já está logado vai direto para o painel. */
export function GuestOnly({
  children,
  redirectTo = "/painel",
}: {
  children: React.ReactNode;
  redirectTo?: string;
}) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated") router.replace(redirectTo);
  }, [status, router, redirectTo]);

  if (status !== "anonymous") return <Spinner />;
  return <>{children}</>;
}
