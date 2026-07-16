import { ConceptDetail } from "@/components/concept-detail";

export default async function ConceptPage({ params }: { params: Promise<{ id: string; slug: string }> }) {
  const { id, slug } = await params;

  return (
    <div className="shell">
      <ConceptDetail courseId={id} slug={slug} />
    </div>
  );
}
