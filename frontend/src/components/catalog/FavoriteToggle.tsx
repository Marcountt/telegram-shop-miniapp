import { useFavoriteStatus, useToggleFavorite } from '../../features/catalog/hooks'
import { Button } from '../ui'
import { QueryError } from './QueryState'

export function FavoriteToggle({ placeId }: { placeId: string }) {
  const favorite = useFavoriteStatus(placeId)
  const toggle = useToggleFavorite(placeId)

  if (favorite.isError) {
    return (
      <div className="favorite-toggle-error">
        <QueryError message={favorite.error.message} onRetry={() => void favorite.refetch()} />
      </div>
    )
  }

  return (
    <Button
      aria-label={favorite.data ? 'Удалить из избранного' : 'Добавить в избранное'}
      aria-pressed={favorite.data ?? false}
      className="favorite-toggle"
      disabled={favorite.isPending || toggle.isPending}
      onClick={() => toggle.mutate(favorite.data ?? false)}
      variant="secondary"
    >
      <span aria-hidden="true">{favorite.data ? '♥' : '♡'}</span>
      <span>{favorite.data ? 'В ИЗБРАННОМ' : 'В ИЗБРАННОЕ'}</span>
    </Button>
  )
}
