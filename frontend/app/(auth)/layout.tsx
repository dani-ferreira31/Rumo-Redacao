import Link from "next/link";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <Link href="/" className="mb-6 text-2xl font-bold text-indigo-700">
        Rumo1000
      </Link>
      <div className="w-full max-w-md">{children}</div>
      <nav className="mt-6 flex gap-4 text-xs text-slate-500">
        <Link href="/termos" className="hover:underline">
          Termos de Uso
        </Link>
        <Link href="/privacidade" className="hover:underline">
          Privacidade
        </Link>
      </nav>
    </div>
  );
}
