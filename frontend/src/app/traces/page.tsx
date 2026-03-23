import { getServerApiToken, serverFetch } from '@/lib/server-auth'
import { TracesClient } from './TracesClient'

export default async function TracesPage() {
  const auth = await getServerApiToken()
  const initialData = auth
    ? await serverFetch<{ traces: any[]; total: number }>('/traces?page=1&per_page=50', auth)
    : null

  return <TracesClient initialData={initialData} />
}
