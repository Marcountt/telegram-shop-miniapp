import { Card, Skeleton } from '../ui'

export function PlaceCardSkeleton() {
  return (
    <Card className="place-card">
      <Skeleton className="place-card__skeleton-image" height={190} />
      <div className="place-card__body">
        <Skeleton height={20} width="72%" />
        <Skeleton height={16} width="45%" />
        <Skeleton height={14} width="86%" />
      </div>
    </Card>
  )
}
