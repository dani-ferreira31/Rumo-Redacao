import type { Metadata } from "next";

import { PaymentsAdmin } from "./payments-admin";

export const metadata: Metadata = { title: "Admin · Pagamentos" };

export default function PaymentsPage() {
  return <PaymentsAdmin />;
}
