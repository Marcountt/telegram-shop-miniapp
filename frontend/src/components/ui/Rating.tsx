interface RatingProps {
  value: number
  count?: number
  className?: string
}

export function Rating({ value, count, className = '' }: RatingProps) {
  const safeValue = Math.min(5, Math.max(0, value))
  const roundedValue = Math.round(safeValue)

  return (
    <span
      aria-label={`Рейтинг ${safeValue.toFixed(1)} из 5${count === undefined ? '' : `, отзывов: ${count}`}`}
      className={`ui-rating ${className}`.trim()}
    >
      <span aria-hidden="true" className="ui-rating__stars">
        {'★'.repeat(roundedValue)}
        <span className="ui-rating__empty">{'★'.repeat(5 - roundedValue)}</span>
      </span>
      <span>{safeValue.toFixed(1)}</span>
      {count !== undefined && <span className="ui-rating__count">({count})</span>}
    </span>
  )
}
