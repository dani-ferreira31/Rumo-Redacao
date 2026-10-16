import Link from "next/link";

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-10">
      <Link href="/" className="text-xl font-bold text-indigo-700">
        Rumo1000
      </Link>
      <div className="mt-6 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
        Modelo em revisão: este texto precisa ser revisado por um advogado antes do lançamento.
        Os trechos entre colchetes devem ser preenchidos.
      </div>
      <article className="legal mt-6 space-y-4 leading-relaxed text-slate-800 [&_h1]:text-2xl [&_h1]:font-semibold [&_h2]:mt-6 [&_h2]:text-lg [&_h2]:font-semibold [&_li]:ml-5 [&_li]:list-disc">
        {children}
      </article>
      <nav className="mt-10 flex gap-4 border-t border-slate-200 pt-4 text-sm">
        <Link href="/termos" className="text-indigo-700 hover:underline">
          Termos de Uso
        </Link>
        <Link href="/privacidade" className="text-indigo-700 hover:underline">
          Política de Privacidade
        </Link>
      </nav>
    </div>
  );
}
