"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert, Button, Card, TextField } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

const schema = z.object({ email: z.email("Informe um e-mail válido.") });
type FormData = z.infer<typeof schema>;

export function ForgotPasswordForm() {
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormData) {
    setError(null);
    const { response, error: apiError } = await api.POST("/api/v1/auth/forgot-password", {
      body: values,
    });
    if (!response.ok) {
      setError(errorMessage(apiError));
      return;
    }
    setSentTo(values.email);
  }

  return (
    <Card>
      <h1 className="mb-4 text-xl font-semibold">Esqueci minha senha</h1>
      {sentTo ? (
        <Alert kind="success">
          Se existir uma conta com <strong>{sentTo}</strong>, você vai receber um e-mail com um link
          para criar uma nova senha. O link vale por 1 hora.
        </Alert>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <p className="text-sm text-slate-600">
            Informe o e-mail da sua conta e enviaremos um link para redefinir a senha.
          </p>
          {error ? <Alert>{error}</Alert> : null}
          <TextField
            label="E-mail"
            type="email"
            autoComplete="email"
            error={errors.email?.message}
            {...register("email")}
          />
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Enviando..." : "Enviar link"}
          </Button>
        </form>
      )}
      <p className="mt-4 text-center text-sm">
        <Link href="/entrar" className="text-indigo-700 hover:underline">
          Voltar para o login
        </Link>
      </p>
    </Card>
  );
}
