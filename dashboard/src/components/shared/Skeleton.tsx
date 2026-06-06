export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton h-4 ${className}`} />
}

export function CardSkeleton() {
  return (
    <div className="card space-y-3">
      <Skeleton className="w-1/3 h-3" />
      <Skeleton className="w-1/2 h-6" />
      <Skeleton className="w-full h-3" />
    </div>
  )
}
