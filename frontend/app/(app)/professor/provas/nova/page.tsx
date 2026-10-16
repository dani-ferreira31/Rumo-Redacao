import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";

import { AssessmentBuilder } from "../../assessment-builder";

export const metadata: Metadata = { title: "Nova prova" };

export default function NewAssessmentPage() {
  return (
    <div className="max-w-7xl">
      <PageHeader title="Nova prova" description="Filtre o banco, adicione as questões e dê um título. A prova nasce fechada: você abre o link quando for aplicar." />
      <AssessmentBuilder />
    </div>
  );
}
