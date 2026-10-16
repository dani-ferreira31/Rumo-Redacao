/** Idade completa em anos para uma data no formato YYYY-MM-DD. */
export function ageFrom(isoDate: string, today?: Date): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  if (!m) return null;
  // Só lê o relógio quando há data: no prerender o campo está vazio.
  const now = today ?? new Date();
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  let age = now.getFullYear() - y;
  const beforeBirthday = now.getMonth() + 1 < mo || (now.getMonth() + 1 === mo && now.getDate() < d);
  if (beforeBirthday) age -= 1;
  return age;
}
