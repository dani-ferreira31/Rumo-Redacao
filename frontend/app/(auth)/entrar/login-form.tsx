"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { GuestOnly } from "@/components/guest-only";
import { Alert, Button, Card, TextField } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { type BillingPublic, brl } from "@/lib/payments";
import { useAuth } from "@/lib/auth";
import { safeNext } from "@/lib/safe-next";

const schema = z.object({
  email: z.email("Informe um e-mail válido."),
  password: z.string().min(1, "Informe sua senha."),
});
type FormData = z.infer<typeof schema>;

export function LoginForm() {
  const params = useSearchParams();
  const { startSession } = useAuth();
  const next = safeNext(params.get("next"));
  const [error, setError] = useState<string | null>(null);
  const [billing, setBilling] = useState<BillingPublic | null>(null);
  useEffect(() => {
    api.GET("/api/v1/billing").then(({ data }) => setBilling(data ?? null));
  }, []);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormData) {
    setError(null);
    const { data, error: apiError } = await api.POST("/api/v1/auth/login", { body: values });
    if (!data) {
      setError(errorMessage(apiError));
      return;
    }
    // GuestOnly redireciona para `next` assim que a sessão fica autenticada.
    await startSession(data);
  }

  return (
    <GuestOnly redirectTo={next}>
      <Card>
        <h1 className="mb-4 text-xl font-semibold">Entrar</h1>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {error ? <Alert>{error}</Alert> : null}
          <TextField
            label="E-mail"
            type="email"
            autoComplete="email"
            error={errors.email?.message}
            {...register("email")}
          />
          <TextField
            label="Senha"
            type="password"
            autoComplete="current-password"
            error={errors.password?.message}
            {...register("password")}
          />
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Entrando..." : "Entrar"}
          </Button>
        </form>
        <div className="mt-4 flex justify-between text-sm">
          <Link href="/esqueci-senha" className="text-indigo-700 hover:underline">
            Esqueci minha senha
          </Link>
          <Link href="/cadastro" className="text-indigo-700 hover:underline">
            Criar conta
          </Link>
        </div>
        {billing?.enabled ? (
          <p className="mt-4 rounded-md bg-slate-50 p-3 text-center text-sm text-slate-600">
            Sem convite? Crie sua conta e assine por <strong>{brl(billing.price_brl)}</strong>, válido por{" "}
            <strong>{billing.period_days} dias</strong> a partir do pagamento (PIX ou cartão). Não renova sozinho.
          </p>
        ) : null}
      </Card>
    </GuestOnly>
  );
}
