import type { Essay } from "@/lib/api";
import { ESSAY_STATUS_LABEL, ESSAY_STATUS_STYLE } from "@/lib/essays";

export function StatusBadge({ status }: { status: Essay["status"] }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${ESSAY_STATUS_STYLE[status]}`}>
      {ESSAY_STATUS_LABEL[status]}
    </span>
  );
}
