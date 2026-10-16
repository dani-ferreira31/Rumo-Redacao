import type { Metadata } from "next";

import { UsersAdmin } from "./users-admin";

export const metadata: Metadata = { title: "Admin · Usuários" };

export default function UsersPage() {
  return <UsersAdmin />;
}
