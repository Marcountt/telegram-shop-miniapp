import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { QueryError, getErrorMessage } from '../../../components/catalog/QueryState'
import { PlaceCard } from '../../../components/catalog/PlaceCard'
import { PlaceCardSkeleton } from '../../../components/catalog/PlaceCardSkeleton'
import { Button, EmptyState, Tag } from '../../../components/ui'
import { useInfiniteSentinel } from '../../../hooks/use-infinite-sentinel'
import { useCategories, usePlaces } from '../hooks'

type SortValue = 'newest' | 'rating' | 'name'

function isSortValue(value: string): value is SortValue {
  return value === 'newest' || value === 'rating' || value === 'name'
}

export function PlacesScreen() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [sheetOpen, setSheetOpen] = useState(false)
  const [draftDistrict, setDraftDistrict] = useState(searchParams.get('district') ?? '')
  const [draftRating, setDraftRating] = useState(searchParams.get('min_rating') ?? '')
  const [draftOpen, setDraftOpen] = useState(searchParams.get('open_now') === 'true')
  const [draftSort, setDraftSort] = useState<'newest' | 'rating' | 'name'>('newest')

  const search = searchParams.get('search') ?? ''
  const categoryId = searchParams.get('category_id') ?? ''
  const district = searchParams.get('district') ?? ''
  const minRating = Number(searchParams.get('min_rating') || 0)
  const openNow = searchParams.get('open_now') === 'true'
  const rawSort = searchParams.get('sort')
  const sort: SortValue =
    rawSort === 'rating' || rawSort === 'name' ? rawSort : 'newest'
  const categories = useCategories()
  const places = usePlaces({
    search,
    categoryId: categoryId || undefined,
    district: district || undefined,
    minRating: minRating || undefined,
    openNow,
    sort,
  })

  const loadMore = useCallback(() => {
    if (places.hasNextPage && !places.isFetchingNextPage) {
      void places.fetchNextPage()
    }
  }, [places.fetchNextPage, places.hasNextPage, places.isFetchingNextPage])
  const sentinelRef = useInfiniteSentinel({
    enabled: Boolean(places.hasNextPage && !places.isFetchingNextPage),
    onLoadMore: loadMore,
  })

  useEffect(() => {
    if (sheetOpen) {
      setDraftDistrict(district)
      setDraftRating(minRating ? String(minRating) : '')
      setDraftOpen(openNow)
      setDraftSort(sort)
    }
  }, [district, minRating, openNow, sheetOpen, sort])

  function updateParam(key: string, value: string) {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    next.delete('cursor')
    setSearchParams(next)
  }

  function applyFilters() {
    const next = new URLSearchParams(searchParams)
    if (draftDistrict.trim()) next.set('district', draftDistrict.trim())
    else next.delete('district')
    if (draftRating) next.set('min_rating', draftRating)
    else next.delete('min_rating')
    if (draftOpen) next.set('open_now', 'true')
    else next.delete('open_now')
    if (draftSort === 'newest') next.delete('sort')
    else next.set('sort', draftSort)
    setSearchParams(next)
    setSheetOpen(false)
  }

  const items = places.data?.pages.flatMap((page) => page.items) ?? []
  const activeFilters = Number(Boolean(district)) + Number(Boolean(minRating)) + Number(openNow)

  return (
    <div className="screen-stack">
      <div className="screen-title-row">
        <div>
          <p className="eyebrow">МЕСТНЫЕ АДРЕСА</p>
          <h1 className="screen-title">КАТАЛОГ</h1>
        </div>
        <Link className="underlined-link" to="/add-business">ДОБАВИТЬ МЕСТО ↗</Link>
      </div>

      <form
        className="search-bar search-bar--compact"
        onSubmit={(event) => event.preventDefault()}
        role="search"
      >
        <span aria-hidden="true">⌕</span>
        <input
          aria-label="Поиск по каталогу"
          onChange={(event) => updateParam('search', event.target.value)}
          placeholder="Название, услуга, адрес"
          value={search}
        />
        {search && (
          <button
            aria-label="Очистить поиск"
            className="icon-button"
            onClick={() => updateParam('search', '')}
            type="button"
          >
            ×
          </button>
        )}
      </form>

      <div className="catalog-controls">
        <Button
          className="filter-button"
          onClick={() => setSheetOpen(true)}
          variant="secondary"
        >
          ФИЛЬТРЫ И СОРТИРОВКА {activeFilters > 0 && <span className="filter-count">{activeFilters}</span>} +
        </Button>
      </div>

      {categoryId && categories.data && (
        <div className="active-filter-row">
          <Tag>{categories.data.find((category) => category.id === categoryId)?.name ?? 'Категория'}</Tag>
          <button
            className="underlined-link"
            onClick={() => updateParam('category_id', '')}
            type="button"
          >
            СБРОСИТЬ ×
          </button>
        </div>
      )}

      {places.isPending ? (
        <div className="place-list">
          {Array.from({ length: 4 }, (_, index) => <PlaceCardSkeleton key={index} />)}
        </div>
      ) : places.isError && items.length === 0 ? (
        <QueryError message={getErrorMessage(places.error)} onRetry={() => void places.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          title="МЕСТ НЕ НАШЛОСЬ"
          description="Измените запрос или сбросьте фильтры."
          action={
            <Button
              onClick={() => setSearchParams(new URLSearchParams())}
              variant="secondary"
            >
              СБРОСИТЬ ФИЛЬТРЫ
            </Button>
          }
        />
      ) : (
        <>
          <p className="result-label">{search ? `РЕЗУЛЬТАТЫ: «${search}»` : 'МЕСТА В ВАШЕМ ГОРОДЕ'}</p>
          <div className="place-list">
            {items.map((place) => <PlaceCard key={place.id} place={place} />)}
          </div>
          <div aria-hidden="true" className="infinite-sentinel" ref={sentinelRef} />
          {places.isFetchingNextPage && (
            <div className="place-list" aria-label="Загружаем ещё места">
              <PlaceCardSkeleton />
              <PlaceCardSkeleton />
            </div>
          )}
          {places.isError && (
            <div className="inline-error" role="alert">
              <p>{getErrorMessage(places.error)}</p>
              <Button onClick={() => void places.refetch()} variant="secondary">
                ЗАГРУЗИТЬ ЕЩЁ РАЗ
              </Button>
            </div>
          )}
        </>
      )}

      {sheetOpen && (
        <div className="sheet-backdrop" onClick={() => setSheetOpen(false)}>
          <section
            aria-labelledby="filter-title"
            aria-modal="true"
            className="filter-sheet"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
          >
            <div className="filter-sheet__handle" />
            <div className="section-heading">
              <h2 id="filter-title">ФИЛЬТРЫ</h2>
              <button
                aria-label="Закрыть фильтры"
                className="icon-button"
                onClick={() => setSheetOpen(false)}
                type="button"
              >
                ×
              </button>
            </div>
            <label className="form-field">
              <span>РАЙОН</span>
              <input
                onChange={(event) => setDraftDistrict(event.target.value)}
                placeholder="Например, Центр"
                value={draftDistrict}
              />
            </label>
            <label className="form-field">
              <span>МИНИМАЛЬНЫЙ РЕЙТИНГ</span>
              <select onChange={(event) => setDraftRating(event.target.value)} value={draftRating}>
                <option value="">ЛЮБОЙ</option>
                <option value="3">ОТ 3 ЗВЁЗД</option>
                <option value="4">ОТ 4 ЗВЁЗД</option>
                <option value="4.5">ОТ 4,5 ЗВЁЗД</option>
              </select>
            </label>
            <label className="form-field">
              <span>СОРТИРОВКА</span>
              <select
                onChange={(event) => {
                  if (isSortValue(event.target.value)) setDraftSort(event.target.value)
                }}
                value={draftSort}
              >
                <option value="newest">СНАЧАЛА НОВЫЕ</option>
                <option value="rating">ПО РЕЙТИНГУ</option>
                <option value="name">ПО НАЗВАНИЮ</option>
              </select>
            </label>
            <label className="switch-field">
              <span>
                <strong>ОТКРЫТО СЕЙЧАС</strong>
                <small>Учитываем график работы места</small>
              </span>
              <input
                checked={draftOpen}
                onChange={(event) => setDraftOpen(event.target.checked)}
                type="checkbox"
              />
            </label>
            <div className="filter-sheet__actions">
              <Button onClick={applyFilters}>ПОКАЗАТЬ МЕСТА</Button>
              <Button
                onClick={() => {
                  setDraftDistrict('')
                  setDraftRating('')
                  setDraftOpen(false)
                }}
                variant="text"
              >
                СБРОСИТЬ
              </Button>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
