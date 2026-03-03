import { Layout } from '@/components/common/Layout'
import { Skeleton } from '@/components/ui/Skeleton'

export default function QualityLoading() {
  return (
    <Layout>
      <div className="p-6">
        <Skeleton className="h-8 w-48 mb-6" />
        <div className="space-y-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
      </div>
    </Layout>
  )
}
