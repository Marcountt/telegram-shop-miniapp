import type { HTMLAttributes } from 'react'

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  height?: string | number
  width?: string | number
  circle?: boolean
}

export function Skeleton({
  height = '1rem',
  width = '100%',
  circle = false,
  className = '',
  style,
  ...props
}: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={`ui-skeleton ${circle ? 'ui-skeleton--circle' : ''} ${className}`.trim()}
      style={{ height, width, ...style }}
      {...props}
    />
  )
}
