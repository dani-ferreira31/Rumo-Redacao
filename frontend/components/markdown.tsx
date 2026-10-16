import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Enunciados e alternativas das questões (Markdown com imagens e tabelas). */
export function Markdown({ children, className = "" }: { children: string; className?: string }) {
  return (
    <div className={`markdown space-y-3 leading-relaxed text-slate-800 ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // eslint-disable-next-line @next/next/no-img-element
          img: ({ src, alt }) => <img src={typeof src === "string" ? src : undefined} alt={alt ?? "Imagem da questão"} className="my-2 max-h-[480px] max-w-full rounded border border-slate-200 bg-white" />,
          a: ({ href, children: c }) => (
            <a href={href} target="_blank" rel="noreferrer noopener" className="text-indigo-700 underline">
              {c}
            </a>
          ),
          table: ({ children: c }) => (
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse text-sm">{c}</table>
            </div>
          ),
          th: ({ children: c }) => <th className="border border-slate-300 bg-slate-50 px-2 py-1 text-left">{c}</th>,
          td: ({ children: c }) => <td className="border border-slate-300 px-2 py-1">{c}</td>,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
