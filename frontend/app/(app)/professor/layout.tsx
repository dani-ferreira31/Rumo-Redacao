import { RequireTeacher } from "@/components/require-teacher";

export default function TeacherLayout({ children }: { children: React.ReactNode }) {
  return <RequireTeacher>{children}</RequireTeacher>;
}
