"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { GuestOnly } from "@/components/guest-only";
import { Alert, Button, Card, TextField } from "@/components/ui";
import { api, errorCode, errorMessage, fieldErrors } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ageFrom } from "@/lib/dates";

const schema = z
  .object({
    name: z.string().trim().min(1, "Informe seu nome.").max(120),
    email: z.email("Informe um e-mail válido."),
    password: z
      .string()
      .min(8, "A senha precisa ter pelo menos 8 caracteres.")
      .max(128, "A senha pode ter no máximo 128 caracteres."),
    birth_date: z.string().min(1, "Informe sua data de nascimento."),
    guardian_consent: z.boolean(),
    accept_terms: z.literal(true, { error: "Você precisa aceitar os termos para continuar." }),
  })
  .superRefine((v, ctx) => {
    const age = ageFrom(v.birth_date);
    if (age === null || age < 0 || age > 120) {
      ctx.addIssue({ code: "custom", path: ["birth_date"], message: "Data de nascimento inválida." });
    } else if (age < 18 && !v.guardian_consent) {
      ctx.addIssue({
        code: "custom",
        path: ["guardian_consent"],
        message: "Menores de 18 anos precisam do consentimento do responsável.",
      });
    }
  });
type FormInput = z.input<typeof schema>;
type FormData = z.output<typeof schema>;

export function RegisterForm() {
  const { startSession } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    control,
    setError: setFieldError,
    formState: { errors, isSubmitting },
  } = useForm<FormInput, unknown, FormData>({
    resolver: zodResolver(schema),
    defaultValues: { guardian_consent: false },
  });

  const age = ageFrom(useWatch({ control, name: "birth_date" }) ?? "");
  const isMinor = age !== null && age >= 0 && age < 18;

  async function onSubmit(values: FormData) {
    setError(null);
    const { data, error: apiError } = await api.POST("/api/v1/auth/register", {
      body: {
        name: values.name,
        email: values.email,
        password: values.password,
        birth_date: values.birth_date,
        guardian_consent: isMinor && values.guardian_consent,
      },
    });
    if (!data) {
      const fields = fieldErrors(apiError);
      for (const [field, message] of Object.entries(fields)) {
        setFieldError(field as keyof FormInput, { message });
      }
      if (errorCode(apiError) === "email_already_registered") {
        setFieldError("email", { message: errorMessage(apiError) });
      } else if (Object.keys(fields).length === 0) {
        setError(errorMessage(apiError));
      }
      return;
    }
    await startSession(data); // GuestOnly leva ao painel

  }

  return (
    <GuestOnly>
      <Card>
        <h1 className="mb-1 text-xl font-semibold">Criar conta</h1>
        <p className="mb-4 text-sm text-slate-600">Gratuito. Use tudo sem limites.</p>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {error ? <Alert>{error}</Alert> : null}
          <TextField label="Nome" autoComplete="name" error={errors.name?.message} {...register("name")} />
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
            autoComplete="new-password"
            hint="Pelo menos 8 caracteres."
            error={errors.password?.message}
            {...register("password")}
          />
          <TextField
            label="Data de nascimento"
            type="date"
            autoComplete="bday"
            error={errors.birth_date?.message}
            {...register("birth_date")}
          />

          {isMinor ? (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
              <label className="flex items-start gap-2 text-sm text-amber-900">
                <input type="checkbox" className="mt-1" {...register("guardian_consent")} />
                <span>
                  Sou menor de 18 anos e meu pai, mãe ou responsável legal autorizou o uso da
                  plataforma e o tratamento dos meus dados.
                </span>
              </label>
              {errors.guardian_consent ? (
                <p className="mt-1 text-sm text-red-600">{errors.guardian_consent.message}</p>
              ) : null}
            </div>
          ) : null}

          <div>
            <label className="flex items-start gap-2 text-sm text-slate-700">
              <input type="checkbox" className="mt-1" {...register("accept_terms")} />
              <span>
                Li e aceito os{" "}
                <a href="/termos" target="_blank" className="text-indigo-700 underline">
                  Termos de Uso
                </a>{" "}
                e a{" "}
                <a href="/privacidade" target="_blank" className="text-indigo-700 underline">
                  Política de Privacidade
                </a>
                . Entendo que o texto e as fotos das minhas redações são enviados a um provedor de
                inteligência artificial (Anthropic) para transcrição e correção.
              </span>
            </label>
            {errors.accept_terms ? (
              <p className="mt-1 text-sm text-red-600">{errors.accept_terms.message}</p>
            ) : null}
          </div>

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Criando conta..." : "Criar conta"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm">
          Já tem conta?{" "}
          <Link href="/entrar" className="text-indigo-700 hover:underline">
            Entrar
          </Link>
        </p>
      </Card>
    </GuestOnly>
  );
}
