"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Alert, Button, Card, TextField } from "@/components/ui";
import { api, errorMessage, fieldErrors } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { BR_TIMEZONES } from "@/lib/timezones";

const schema = z.object({
  name: z.string().trim().min(1, "Informe seu nome.").max(120),
  timezone: z.string().min(1),
  target_exam_year: z.string().refine((v) => v === "" || /^\d{4}$/.test(v), "Ano inválido."),
  email_reminders_enabled: z.boolean(),
});
type FormData = z.infer<typeof schema>;

export function ProfileForm() {
  const { user, setUser } = useAuth();
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting, isDirty },
    reset,
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    values: user
      ? {
          name: user.name,
          timezone: user.timezone,
          target_exam_year: user.target_exam_year ? String(user.target_exam_year) : "",
          email_reminders_enabled: user.email_reminders_enabled,
        }
      : undefined,
  });

  if (!user) return null;

  const timezoneOptions = BR_TIMEZONES.some((tz) => tz.value === user.timezone)
    ? BR_TIMEZONES
    : [{ value: user.timezone, label: user.timezone }, ...BR_TIMEZONES];

  async function onSubmit(values: FormData) {
    setMessage(null);
    const { data, error } = await api.PATCH("/api/v1/me", {
      body: {
        name: values.name,
        timezone: values.timezone,
        target_exam_year: values.target_exam_year ? Number(values.target_exam_year) : null,
        email_reminders_enabled: values.email_reminders_enabled,
      },
    });
    if (!data) {
      const fields = fieldErrors(error);
      for (const [field, msg] of Object.entries(fields)) {
        setError(field as keyof FormData, { message: msg });
      }
      setMessage({ kind: "error", text: errorMessage(error) });
      return;
    }
    setUser(data);
    reset();
    setMessage({ kind: "success", text: "Alterações salvas." });
  }

  return (
    <Card>
      <h2 className="mb-4 text-lg font-semibold">Seus dados</h2>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {message ? <Alert kind={message.kind}>{message.text}</Alert> : null}
        <TextField label="Nome" autoComplete="name" error={errors.name?.message} {...register("name")} />
        <div>
          <p className="mb-1 text-sm font-medium text-slate-700">E-mail</p>
          <p className="text-slate-900">
            {user.email}{" "}
            <span className={user.email_verified ? "text-green-700" : "text-amber-700"}>
              ({user.email_verified ? "confirmado" : "não confirmado"})
            </span>
          </p>
        </div>
        <div>
          <label htmlFor="timezone" className="mb-1 block text-sm font-medium text-slate-700">
            Fuso horário
          </label>
          <select
            id="timezone"
            className="block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900 shadow-sm focus:ring-2 focus:ring-indigo-500"
            {...register("timezone")}
          >
            {timezoneOptions.map((tz) => (
              <option key={tz.value} value={tz.value}>
                {tz.label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-sm text-slate-500">Usado nos lembretes do cronograma.</p>
          {errors.timezone ? <p className="mt-1 text-sm text-red-600">{errors.timezone.message}</p> : null}
        </div>
        <TextField
          label="Ano em que vai fazer o ENEM"
          type="number"
          inputMode="numeric"
          min={2020}
          max={2100}
          placeholder="Ex.: 2027"
          error={errors.target_exam_year?.message}
          {...register("target_exam_year")}
        />
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" {...register("email_reminders_enabled")} />
          Receber lembretes de estudo por e-mail
        </label>
        <Button type="submit" disabled={isSubmitting || !isDirty}>
          {isSubmitting ? "Salvando..." : "Salvar"}
        </Button>
      </form>
    </Card>
  );
}
