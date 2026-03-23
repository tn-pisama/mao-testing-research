import { getServerApiToken, serverFetch } from '@/lib/server-auth'
import { QualityClient } from './QualityClient'

export default async function QualityPage() {
  const auth = await getServerApiToken()
  const data = auth
    ? await serverFetch<{ assessments: any[]; total: number }>(
        '/enterprise/quality/tenants/{tenant_id}/assessments?page=1&page_size=10', auth
      )
    : null

  return (
    <QualityClient
      initialAssessments={data?.assessments ?? []}
      initialTotal={data?.total ?? 0}
    />
  )
}
