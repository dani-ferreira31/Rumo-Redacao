"use client";

import { useState } from "react";

import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function VerifyEmailBanner() {
  const { user } = useAuth();
  const [state, setState] = useState<"idle" | "sending" | "sent" | string>("idle");

  if (!user || user.email_verified) return null;

  async function resend() {
    setState("sending");
    const { response, error } = await api.POST("/api/v1/auth/resend-verification");
    setState(response.ok ? "sent" : errorMessage(error));
  }

  return (
    <div role="status" className="mb-6 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
      Confirme seu e-mail (<strong>{user.email}</strong>) para enviar redações.{" "}
      {state === "sent" ? (
        <span>Enviamos um novo link.</span>
      ) : state === "idle" || state === "sending" ? (
        <button
          type="button"
          onClick={resend}
          disabled={state === "sending"}
          className="font-medium underline disabled:opacity-60"
        >
          {state === "sending" ? "Enviando..." : "Reenviar e-mail"}
        </button>
      ) : (
        <span>{state}</span>
      )}
    </div>
  );
}
