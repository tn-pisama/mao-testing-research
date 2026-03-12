import { Card } from '@/components/ui/Card'

export function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ElementType
  title: string
  description: string
}) {
  return (
    <Card>
      <div className="text-center py-12 px-4">
        <Icon size={40} className="mx-auto mb-4 text-zinc-600 opacity-50" />
        <p className="text-zinc-300 mb-2 font-medium">{title}</p>
        <p className="text-sm text-zinc-500">{description}</p>
      </div>
    </Card>
  )
}
