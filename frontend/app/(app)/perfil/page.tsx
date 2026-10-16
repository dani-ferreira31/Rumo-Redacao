import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";

import { DeleteAccount } from "./delete-account";
import { ProfileForm } from "./profile-form";

export const metadata: Metadata = { title: "Perfil" };

export default function ProfilePage() {
  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Perfil" />
      <ProfileForm />
      <DeleteAccount />
    </div>
  );
}
