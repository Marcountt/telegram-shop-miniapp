import { Link } from 'react-router'
import { Card, Rating, Tag } from '../ui'
import type { PlaceSummary } from '../../features/catalog/types'

export function photoUrl(place: PlaceSummary): string | undefined {
  const firstPhoto = place.photos[0]
  if (!firstPhoto) return undefined
  const url = firstPhoto.url ?? firstPhoto.src
  return typeof url === 'string' ? url : undefined
}

export function PlaceCard({ place }: { place: PlaceSummary }) {
  const image = photoUrl(place)

  return (
    <Link className="place-card-link" to={`/places/${place.id}`}>
      <Card className="place-card">
        <div className="place-card__image-wrap">
          {image ? (
            <img className="place-card__image" src={image} alt={place.name} loading="lazy" />
          ) : (
            <div className="place-card__image-placeholder" aria-hidden="true">LOCAL</div>
          )}
          {place.district && <Tag className="place-card__district">{place.district}</Tag>}
        </div>
        <div className="place-card__body">
          <div className="place-card__title-row">
            <h2>{place.name}</h2>
            <span className="place-card__arrow" aria-hidden="true">↗</span>
          </div>
          <Rating value={Number(place.rating_cache)} count={place.review_count} />
          <p className="place-card__address">{place.address || 'Адрес не указан'}</p>
        </div>
      </Card>
    </Link>
  )
}
