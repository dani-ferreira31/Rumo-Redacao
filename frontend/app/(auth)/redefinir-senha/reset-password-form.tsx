"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert, Button, Card, TextField } from "@/components/ui";
import { api, errorMessage, fieldErrors } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const schema = z
  .object({
    new_password: z
      .string()
      .min(8, "A senha precisa ter pelo menos 8 caracteres.")
      .max(128, "A senha pode ter no máximo 128 caracteres."),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, {
    path: ["confirm"],
    message: "As senhas não conferem.",
  });
type FormData = z.infer<typeof schema>;

export function ResetPasswordForm() {
  const token = useSearchParams().get("token");
  const { clearSession } = useAuth();
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormData) {
    if (!token) return;
    setError(null);
    const { response, error: apiError } = await api.POST("/api/v1/auth/reset-password", {
      body: { token, new_password: values.new_password },
    });
    if (!response.ok) {
      setError(fieldErrors(apiError).new_password ?? errorMessage(apiError));
      return;
    }
    clearSession(); // a API encerrou todas as sessões
    setDone(true);
  }

  return (
    <Card>
      <h1 className="mb-4 text-xl font-semibold">Criar nova senha</h1>
      {!token ? (
        <Alert>
          Link incompleto. <Link href="/esqueci-senha" className="underline">Peça um novo link</Link>.
        </Alert>
      ) : done ? (
        <div className="space-y-4">
          <Alert kind="success">Senha alterada! Por segurança, encerramos suas outras sessões.</Alert>
          <Link href="/entrar" className="block text-center text-indigo-700 hover:underline">
            Entrar com a nova senha
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {error ? (
            <Alert>
              {error}{" "}
              <Link href="/esqueci-senha" className="underline">
                Pedir novo link
              </Link>
            </Alert>
          ) : null}
          <TextField
            label="Nova senha"
            type="password"
            autoComplete="new-password"
            hint="Pelo menos 8 caracteres."
            error={errors.new_password?.message}
            {...register("new_password")}
          />
          <TextField
            label="Confirme a nova senha"
            type="password"
            autoComplete="new-password"
            error={errors.confirm?.message}
            {...register("confirm")}
          />
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Salvando..." : "Salvar nova senha"}
          </Button>
        </form>
      )}
    </Card>
  );
}
