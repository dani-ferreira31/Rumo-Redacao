import type { Metadata } from "next";

import { ThemesAdmin } from "./themes-admin";

export const metadata: Metadata = { title: "Temas de redação" };

export default function Page() {
  return <ThemesAdmin />;
}
