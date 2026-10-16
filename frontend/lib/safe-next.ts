/** Aceita só caminhos internos no parâmetro ?next= (evita open redirect). */
export function safeNext(next: string | null, fallback = "/painel"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) return fallback;
  return next;
}
