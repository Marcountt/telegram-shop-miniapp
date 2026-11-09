import { useCallback } from 'react'
import { Link, useNavigate } from 'react-router'
import { PlaceCard } from '../../../components/catalog/PlaceCard'
import { PlaceCardSkeleton } from '../../../components/catalog/PlaceCardSkeleton'
import { getErrorMessage, QueryError } from '../../../components/catalog/QueryState'
import { Button, EmptyState } from '../../../components/ui'
import { useInfiniteSentinel } from '../../../hooks/use-infinite-sentinel'
import { useFavorites } from '../hooks'

export function FavoritesScreen() {
  const favorites = useFavorites()
  const navigate = useNavigate()
  const loadMore = useCallback(() => {
    if (favorites.hasNextPage && !favorites.isFetchingNextPage) {
      void favorites.fetchNextPage()
    }
  }, [favorites.fetchNextPage, favorites.hasNextPage, favorites.isFetchingNextPage])
  const sentinelRef = useInfiniteSentinel({
    enabled: Boolean(favorites.hasNextPage && !favorites.isFetchingNextPage),
    onLoadMore: loadMore,
  })

  const items = favorites.data?.pages.flatMap((page) => page.items) ?? []

  return (
    <div className="screen-stack">
      <div className="screen-title-row">
        <div>
          <p className="eyebrow">ВАША ЛИЧНАЯ ПОДБОРКА</p>
          <h1 className="screen-title">ИЗБРАННОЕ</h1>
        </div>
        <Link className="underlined-link" to="/places">В КАТАЛОГ ↗</Link>
      </div>

      {favorites.isPending ? (
        <div className="place-list">
          {Array.from({ length: 3 }, (_, index) => <PlaceCardSkeleton key={index} />)}
        </div>
      ) : favorites.isError && items.length === 0 ? (
        <QueryError message={getErrorMessage(favorites.error)} onRetry={() => void favorites.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          title="ИЗБРАННОЕ ПОКА ПУСТО"
          description="Сохраняйте места, которые понравились, чтобы вернуться к ним позже."
          action={<Button onClick={() => navigate('/places')}>ОТКРЫТЬ КАТАЛОГ</Button>}
          icon={<span aria-hidden="true">♡</span>}
        />
      ) : (
        <>
          <p className="result-label">{items.length} {items.length === 1 ? 'МЕСТО' : 'МЕСТА'}</p>
          <div className="place-list">
            {items.map((place) => <PlaceCard key={place.id} place={place} />)}
          </div>
          <div aria-hidden="true" className="infinite-sentinel" ref={sentinelRef} />
          {favorites.isFetchingNextPage && (
            <div className="place-list"><PlaceCardSkeleton /></div>
          )}
          {favorites.isError && (
            <div className="inline-error" role="alert">
              <p>{getErrorMessage(favorites.error)}</p>
              <Button onClick={() => void favorites.refetch()} variant="secondary">
                ЗАГРУЗИТЬ ЕЩЁ РАЗ
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
