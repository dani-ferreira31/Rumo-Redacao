import type { Metadata } from "next";

import { TeacherHome } from "./teacher-home";

export const metadata: Metadata = { title: "Professor" };

export default function TeacherPage() {
  return <TeacherHome />;
}
