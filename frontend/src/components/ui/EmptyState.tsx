import type { ReactNode } from 'react'

interface EmptyStateProps {
  title: string
  description?: string
  icon?: ReactNode
  action?: ReactNode
}

export function EmptyState({
  title,
  description,
  icon,
  action,
}: EmptyStateProps) {
  return (
    <section className="ui-empty-state" aria-live="polite">
      {icon && <div className="ui-empty-state__icon">{icon}</div>}
      <h2 className="ui-empty-state__title">{title}</h2>
      {description && <p className="ui-empty-state__description">{description}</p>}
      {action && <div className="ui-empty-state__action">{action}</div>}
    </section>
  )
}
