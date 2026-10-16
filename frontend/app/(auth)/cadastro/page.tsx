import type { Metadata } from "next";

import { RegisterForm } from "./register-form";

export const metadata: Metadata = { title: "Criar conta" };

export default function RegisterPage() {
  return <RegisterForm />;
}
