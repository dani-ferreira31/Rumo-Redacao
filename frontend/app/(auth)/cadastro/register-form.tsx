"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { GuestOnly } from "@/components/guest-only";
import { Alert, Button, Card, Spinner, TextField } from "@/components/ui";
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

const ROLE_LABEL: Record<string, string> = { student: "aluno", teacher: "professor" };

const brl = (v: number) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

type Billing = { enabled: boolean; price_brl: number; period_days: number };

/** Com `?convite=<código>`: conta de aluno ou professor, sem pagamento. Sem convite: só
 * se o cadastro pago estiver aberto (a conta é criada e o aluno assina em seguida). */
export function RegisterForm() {
  const code = useSearchParams().get("convite")?.trim() ?? "";
  const [invite, setInvite] = useState<{ role: string } | "invalid" | null>(null);
  const [billing, setBilling] = useState<Billing | null>(null);

  useEffect(() => {
    if (code) {
      api
        .GET("/api/v1/invites/{code}", { params: { path: { code } } })
        .then(({ data }) => setInvite(data ?? "invalid"));
    } else {
      api.GET("/api/v1/billing").then(({ data }) => setBilling(data ?? { enabled: false, price_brl: 0, period_days: 0 }));
    }
  }, [code]);

  if (code && invite && invite !== "invalid") return <SignupForm code={code} role={invite.role} />;
  if (!code && billing?.enabled) return <SignupForm code={null} role="student" billing={billing} />;
  if ((code && !invite) || (!code && !billing)) return <Spinner label="Carregando..." />;

  return (
    <GuestOnly>
      <Card>
        <h1 className="mb-2 text-xl font-semibold">Cadastro por convite</h1>
        {code ? (
          <Alert>
            Este convite não é válido: pode ter expirado, sido revogado ou atingido o limite de
            usos. Peça um link novo a quem te convidou.
          </Alert>
        ) : (
          <p className="text-sm text-slate-600">
            Para criar uma conta você precisa do link de convite enviado pela escola ou pelo
            professor. Abra o link que você recebeu.
          </p>
        )}
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

function SignupForm({ code, role, billing }: { code: string | null; role: string; billing?: Billing }) {
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
        invite_code: code ?? undefined,
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
        <p className="mb-4 text-sm text-slate-600">
          {code ? (
            <>
              Você foi convidado como <strong>{ROLE_LABEL[role] ?? role}</strong>.
            </>
          ) : billing ? (
            <>
              Depois de criar a conta, você assina por{" "}
              <strong>{brl(billing.price_brl)}</strong>, válido por{" "}
              <strong>{billing.period_days} dias</strong> a partir do pagamento, com PIX ou cartão.
              Não renova sozinho: avisamos por e-mail antes de vencer.
            </>
          ) : null}
        </p>
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
                inteligência artificial para transcrição e correção.
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
