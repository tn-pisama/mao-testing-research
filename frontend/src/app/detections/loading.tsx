import { Layout } from '@/components/common/Layout'
import { Skeleton } from '@/components/ui/Skeleton'

export default function DetectionsLoading() {
  return (
    <Layout>
      <div className="p-6">
        <Skeleton className="h-8 w-48 mb-6" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-96 rounded-xl" />
      </div>
    </Layout>
  )
}
