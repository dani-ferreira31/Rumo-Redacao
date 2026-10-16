export const WEEKDAYS = [
  { n: 1, short: "Seg", long: "Segunda" },
  { n: 2, short: "Ter", long: "Terça" },
  { n: 3, short: "Qua", long: "Quarta" },
  { n: 4, short: "Qui", long: "Quinta" },
  { n: 5, short: "Sex", long: "Sexta" },
  { n: 6, short: "Sáb", long: "Sábado" },
  { n: 7, short: "Dom", long: "Domingo" },
];

export const SLOT = 30; // minutos por linha da grade

/** "HH:MM" ou "HH:MM:SS" → minutos desde 00:00. */
export function toMin(t: string): number {
  const [h, m] = t.split(":").map(Number);
  return h * 60 + m;
}

/** minutos → "HH:MM" (formato aceito pela API). */
export function toHHMM(min: number): string {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export const REMINDER_OPTIONS = [
  { value: "", label: "Sem lembrete" },
  { value: "0", label: "Na hora" },
  { value: "5", label: "5 min antes" },
  { value: "10", label: "10 min antes" },
  { value: "15", label: "15 min antes" },
  { value: "30", label: "30 min antes" },
  { value: "60", label: "1 h antes" },
  { value: "120", label: "2 h antes" },
];

/** ISO 8601: segunda = 1 ... domingo = 7. */
export function isoWeekday(d = new Date()): number {
  return ((d.getDay() + 6) % 7) + 1;
}
