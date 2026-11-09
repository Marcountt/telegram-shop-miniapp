import { useCallback, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import { useAddReview, usePlace, useReviews } from '../hooks'
import { getErrorMessage, QueryError } from '../../../components/catalog/QueryState'
import { Button, Card, EmptyState, Rating, Skeleton } from '../../../components/ui'
import { useInfiniteSentinel } from '../../../hooks/use-infinite-sentinel'

export function ReviewsScreen() {
  const { placeId = '' } = useParams()
  const place = usePlace(placeId)
  const reviews = useReviews(placeId)
  const addReview = useAddReview(placeId)
  const loadMore = useCallback(() => {
    if (reviews.hasNextPage && !reviews.isFetchingNextPage) {
      void reviews.fetchNextPage()
    }
  }, [reviews.fetchNextPage, reviews.hasNextPage, reviews.isFetchingNextPage])
  const sentinelRef = useInfiniteSentinel({
    enabled: Boolean(reviews.hasNextPage && !reviews.isFetchingNextPage),
    onLoadMore: loadMore,
  })

  if (place.isPending) {
    return (
      <div className="screen-stack">
        <Skeleton height={34} width="70%" />
        <Skeleton height={120} />
      </div>
    )
  }

  if (place.isError) {
    return <QueryError message={getErrorMessage(place.error)} onRetry={() => void place.refetch()} />
  }

  const items = reviews.data?.pages.flatMap((page) => page.items) ?? []

  return (
    <div className="screen-stack">
      <div className="screen-title-row">
        <div>
          <p className="eyebrow">МНЕНИЯ ПОСЕТИТЕЛЕЙ</p>
          <h1 className="screen-title">ОТЗЫВЫ</h1>
          <p className="detail-copy">{place.data.name}</p>
        </div>
        <Link className="underlined-link" to={`/places/${placeId}`}>К МЕСТУ ↗</Link>
      </div>

      {place.data.review_count > 0 && (
        <div className="review-summary">
          <Rating value={Number(place.data.rating_cache)} count={place.data.review_count} />
          <span>СРЕДНЯЯ ОЦЕНКА</span>
        </div>
      )}

      <section aria-label="Отзывы" className="review-list">
        {reviews.isPending ? (
          Array.from({ length: 3 }, (_, index) => (
            <Card className="review-card" key={index}>
              <Skeleton height={20} width="50%" />
              <Skeleton height={15} width="35%" />
              <Skeleton height={45} />
            </Card>
          ))
        ) : reviews.isError && items.length === 0 ? (
          <QueryError message={getErrorMessage(reviews.error)} onRetry={() => void reviews.refetch()} />
        ) : items.length === 0 ? (
          <EmptyState
            title="ОТЗЫВОВ ПОКА НЕТ"
            description="Расскажите о своём опыте — это поможет другим."
          />
        ) : (
          items.map((review) => (
            <Card className="review-card" key={review.id}>
              <div className="review-card__heading">
                <strong>{review.user_name || 'ПОСЕТИТЕЛЬ'}</strong>
                <time dateTime={review.created_at}>
                  {new Intl.DateTimeFormat('ru-RU', {
                    day: '2-digit',
                    month: 'long',
                    year: 'numeric',
                  }).format(new Date(review.created_at))}
                </time>
              </div>
              <Rating value={review.rating} />
              {review.comment && <p className="detail-copy">{review.comment}</p>}
            </Card>
          ))
        )}
        <div aria-hidden="true" className="infinite-sentinel" ref={sentinelRef} />
        {reviews.isFetchingNextPage && (
          <Card className="review-card"><Skeleton height={78} /></Card>
        )}
        {reviews.isError && items.length > 0 && (
          <div className="inline-error" role="alert">
            <p>{getErrorMessage(reviews.error)}</p>
            <Button onClick={() => void reviews.refetch()} variant="secondary">
              ЗАГРУЗИТЬ ЕЩЁ РАЗ
            </Button>
          </div>
        )}
      </section>

      <section className="detail-section" id="форма">
        <div className="section-heading">
          <h2>ВАШ ОТЗЫВ</h2>
        </div>
        {addReview.isSuccess ? (
          <EmptyState
            title="СПАСИБО!"
            description="Ваш отзыв добавлен. Рейтинг места обновлён."
            action={
              <Button onClick={() => addReview.reset()} variant="secondary">
                ЗАКРЫТЬ
              </Button>
            }
          />
        ) : (
          <ReviewForm
            error={addReview.isError ? getErrorMessage(addReview.error) : undefined}
            isPending={addReview.isPending}
            onSubmit={(rating, comment) => addReview.mutate({ rating, comment })}
          />
        )}
      </section>
    </div>
  )
}

interface ReviewFormProps {
  error?: string
  isPending: boolean
  onSubmit: (rating: number, comment: string) => void
}

export function ReviewForm({ error, isPending, onSubmit }: ReviewFormProps) {
  const [rating, setRating] = useState(5)
  const [comment, setComment] = useState('')

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSubmit(rating, comment.trim())
  }

  return (
    <form className="review-form" onSubmit={submit}>
      <fieldset className="rating-picker" disabled={isPending}>
        <legend>ВАША ОЦЕНКА</legend>
        <div>
          {Array.from({ length: 5 }, (_, index) => {
            const value = index + 1
            return (
              <button
                aria-label={`${value} из 5`}
                aria-pressed={rating === value}
                className={value <= rating ? 'rating-picker__star rating-picker__star--active' : 'rating-picker__star'}
                key={value}
                onClick={() => setRating(value)}
                type="button"
              >
                ★
              </button>
            )
          })}
        </div>
      </fieldset>
      <label className="form-field">
        <span>КОММЕНТАРИЙ</span>
        <textarea
          maxLength={5000}
          onChange={(event) => setComment(event.target.value)}
          placeholder="Поделитесь впечатлениями"
          rows={4}
          value={comment}
        />
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <Button disabled={isPending} type="submit">
        {isPending ? 'ОТПРАВЛЯЕМ…' : 'ОСТАВИТЬ ОТЗЫВ'}
      </Button>
    </form>
  )
}
