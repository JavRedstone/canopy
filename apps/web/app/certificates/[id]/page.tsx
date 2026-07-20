import { PageShell } from "@/components/page-shell";
import { PublicCertificateView } from "@/components/public-certificate-view";

export default async function PublicCertificatePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <PageShell maxWidth={720}>
      <PublicCertificateView certificateId={id} />
    </PageShell>
  );
}
