import { Layout } from '@/components/common/Layout'
import { Skeleton } from '@/components/ui/Skeleton'

export default function TracesLoading() {
  return (
    <Layout>
      <div className="p-6">
        <Skeleton className="h-8 w-32 mb-6" />
        <Skeleton className="h-10 w-full mb-4 rounded-lg" />
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-16 rounded-lg" />
          ))}
        </div>
      </div>
    </Layout>
  )
}
