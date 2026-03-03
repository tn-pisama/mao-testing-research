import { Layout } from '@/components/common/Layout'
import { Skeleton } from '@/components/ui/Skeleton'

export default function WorkflowDetailLoading() {
  return (
    <Layout>
      <div className="p-6">
        <Skeleton className="h-6 w-20 mb-4" />
        <Skeleton className="h-8 w-72 mb-2" />
        <div className="flex gap-3 mb-6">
          <Skeleton className="h-6 w-16 rounded" />
          <Skeleton className="h-6 w-20 rounded" />
        </div>
        <Skeleton className="h-[600px] rounded-xl" />
      </div>
    </Layout>
  )
}
