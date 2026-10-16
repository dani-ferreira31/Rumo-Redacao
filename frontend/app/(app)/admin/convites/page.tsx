import type { Metadata } from "next";

import { InvitesAdmin } from "./invites-admin";

export const metadata: Metadata = { title: "Admin · Convites" };

export default function InvitesPage() {
  return <InvitesAdmin />;
}
