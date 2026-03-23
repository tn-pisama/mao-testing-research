import { getServerApiToken, serverFetch } from '@/lib/server-auth'
import { DetectionsClient } from './DetectionsClient'

export default async function DetectionsPage() {
  const auth = await getServerApiToken()
  const initialData = auth
    ? await serverFetch<{ items: any[]; total: number; page: number; per_page: number }>(
        '/detections?page=1&per_page=20', auth
      )
    : null

  return <DetectionsClient initialData={initialData} />
}
