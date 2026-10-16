import { AdminNav } from "@/components/admin/admin-nav";
import { RequireAdmin } from "@/components/require-admin";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAdmin>
      <div className="md:grid md:grid-cols-[14rem_minmax(0,1fr)] md:gap-8">
        <aside className="mb-6 border-b border-slate-200 pb-3 md:sticky md:top-6 md:mb-0 md:self-start md:border-b-0 md:pb-0">
          <p className="mb-3 hidden px-3 text-sm font-semibold text-slate-900 md:block">Administração</p>
          <AdminNav />
        </aside>
        <div className="min-w-0">{children}</div>
      </div>
    </RequireAdmin>
  );
}
