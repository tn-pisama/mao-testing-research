import { Layout } from '@/components/common/Layout'
import { Skeleton } from '@/components/ui/Skeleton'

export default function TraceDetailLoading() {
  return (
    <Layout>
      <div className="p-6">
        <Skeleton className="h-6 w-24 mb-4" />
        <Skeleton className="h-8 w-64 mb-2" />
        <Skeleton className="h-4 w-48 mb-6" />
        <div className="flex gap-2 mb-6">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-9 w-24 rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-96 rounded-xl" />
      </div>
    </Layout>
  )
}
