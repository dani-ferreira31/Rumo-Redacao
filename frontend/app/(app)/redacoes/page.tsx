import type { Metadata } from "next";

import { EssaysHome } from "./essays-home";

export const metadata: Metadata = { title: "Redações" };

export default function EssaysPage() {
  return <EssaysHome />;
}
