import { Layout } from "@/components/common/Layout"
import { Skeleton } from "@/components/ui/Skeleton"

export default function Loading() {
  return (
    <Layout>
      <div className="p-6">
        <Skeleton className="h-8 w-48 mb-6" />
        <div className="grid lg:grid-cols-2 gap-6 mb-6">
          <Skeleton className="h-64 rounded-xl" />
          <Skeleton className="h-64 rounded-xl" />
        </div>
        <Skeleton className="h-64 rounded-xl" />
      </div>
    </Layout>
  )
}
