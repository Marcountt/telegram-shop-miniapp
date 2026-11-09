import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { FavoriteToggle } from '../../../components/catalog/FavoriteToggle'
import { getErrorMessage, QueryError } from '../../../components/catalog/QueryState'
import { Button, Card, Rating, Skeleton, Tag } from '../../../components/ui'
import { usePlace } from '../hooks'

const dayLabels: Record<string, string> = {
  monday: 'ПОНЕДЕЛЬНИК',
  tuesday: 'ВТОРНИК',
  wednesday: 'СРЕДА',
  thursday: 'ЧЕТВЕРГ',
  friday: 'ПЯТНИЦА',
  saturday: 'СУББОТА',
  sunday: 'ВОСКРЕСЕНЬЕ',
}

function telegramUrl(value: string): string {
  if (/^https?:\/\//i.test(value)) return value
  return `https://t.me/${value.replace(/^@/, '')}`
}

export function PlaceScreen() {
  const { placeId = '' } = useParams()
  const placeQuery = usePlace(placeId)
  const [photoIndex, setPhotoIndex] = useState(0)

  if (placeQuery.isPending) {
    return (
      <div className="screen-stack">
        <Skeleton height={280} />
        <Skeleton height={36} width="70%" />
        <Skeleton height={20} width="45%" />
        <Skeleton height={100} />
      </div>
    )
  }

  if (placeQuery.isError) {
    return <QueryError message={getErrorMessage(placeQuery.error)} onRetry={() => void placeQuery.refetch()} />
  }

  const place = placeQuery.data
  const images = place.photos
    .map((photo) => ({
      src: photo.url ?? photo.src,
      alt: photo.alt,
    }))
    .filter((photo): photo is { src: string; alt: unknown } => typeof photo.src === 'string')
  const activeImage = images[photoIndex]
  const coordinates =
    place.latitude !== null && place.longitude !== null
      ? `${place.latitude},${place.longitude}`
      : undefined
  const directionsUrl = coordinates
    ? `https://maps.google.com/?q=${encodeURIComponent(coordinates)}`
    : place.address
      ? `https://maps.google.com/?q=${encodeURIComponent(place.address)}`
      : undefined

  return (
    <article className="screen-stack place-detail">
      <div className="place-gallery">
        {activeImage ? (
          <img
            alt={typeof activeImage.alt === 'string' ? activeImage.alt : place.name}
            className="place-gallery__image"
            src={activeImage.src}
          />
        ) : (
          <div className="place-gallery__placeholder">
            <span>LOCAL CATALOG</span>
            <strong>{place.name}</strong>
          </div>
        )}
        {images.length > 1 && (
          <>
            <button
              aria-label="Предыдущее фото"
              className="gallery-arrow gallery-arrow--previous"
              onClick={() => setPhotoIndex((photoIndex - 1 + images.length) % images.length)}
              type="button"
            >
              ‹
            </button>
            <button
              aria-label="Следующее фото"
              className="gallery-arrow gallery-arrow--next"
              onClick={() => setPhotoIndex((photoIndex + 1) % images.length)}
              type="button"
            >
              ›
            </button>
            <span className="place-gallery__count">
              {photoIndex + 1} / {images.length}
            </span>
          </>
        )}
      </div>

      <div className="place-detail__heading">
        {place.category && <Tag>{place.category.name}</Tag>}
        <h1>{place.name}</h1>
        <Rating value={Number(place.rating_cache)} count={place.review_count} />
        {place.address && <p className="place-detail__address">{place.address}</p>}
        {place.district && <p className="eyebrow">{place.district}</p>}
      </div>

      <FavoriteToggle placeId={place.id} />

      {place.description && (
        <section className="detail-section">
          <h2>О МЕСТЕ</h2>
          <p className="detail-copy">{place.description}</p>
        </section>
      )}

      {place.working_hours && (
        <section className="detail-section">
          <h2>ЧАСЫ РАБОТЫ</h2>
          <Card className="hours-card">
            {Object.entries(dayLabels).map(([key, label]) => {
              const intervals = place.working_hours?.[key] ?? []
              return (
                <div className="hours-row" key={key}>
                  <span>{label}</span>
                  <span>
                    {intervals.length
                      ? intervals.map((item) => `${item.open.slice(0, 5)}–${item.close.slice(0, 5)}`).join(', ')
                      : 'ЗАКРЫТО'}
                  </span>
                </div>
              )
            })}
          </Card>
        </section>
      )}

      <section className="detail-section">
        <div className="section-heading">
          <h2>ОТЗЫВЫ</h2>
          <Link className="underlined-link" to={`/places/${place.id}/reviews`}>
            ВСЕ ОТЗЫВЫ ↗
          </Link>
        </div>
        <p className="detail-copy">
          {place.review_count
            ? `${place.review_count} ${place.review_count === 1 ? 'отзыв' : 'отзывов'} от посетителей`
            : 'Пока нет отзывов. Станьте первым.'}
        </p>
        <Link className="underlined-link" to={`/places/${place.id}/reviews#форма`}>
          ОСТАВИТЬ ОТЗЫВ ↗
        </Link>
      </section>

      <section className="detail-section">
        <h2>СВЯЗАТЬСЯ</h2>
        <div className="contact-actions">
          {place.phone && (
            <a className="contact-action" href={`tel:${place.phone}`}>
              <span aria-hidden="true">↗</span> ПОЗВОНИТЬ
            </a>
          )}
          {place.telegram && (
            <a
              className="contact-action"
              href={telegramUrl(place.telegram)}
              rel="noreferrer"
              target="_blank"
            >
              <span aria-hidden="true">↗</span> НАПИСАТЬ В TELEGRAM
            </a>
          )}
          {directionsUrl && (
            <a
              className="contact-action"
              href={directionsUrl}
              rel="noreferrer"
              target="_blank"
            >
              <span aria-hidden="true">↗</span> КАК ДОБРАТЬСЯ
            </a>
          )}
          {place.website && (
            <a
              className="contact-action"
              href={place.website}
              rel="noreferrer"
              target="_blank"
            >
              <span aria-hidden="true">↗</span> САЙТ
            </a>
          )}
        </div>
        {!place.phone && !place.telegram && !directionsUrl && !place.website && (
          <p className="detail-copy">Контактные данные пока не указаны.</p>
        )}
      </section>

      <Button className="back-to-list" onClick={() => window.history.back()} variant="text">
        ← НАЗАД К СПИСКУ
      </Button>
    </article>
  )
}
