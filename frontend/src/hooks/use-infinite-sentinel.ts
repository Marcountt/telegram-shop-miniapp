import { useEffect, useRef } from 'react'

interface InfiniteSentinelOptions {
  enabled: boolean
  onLoadMore: () => void
}

export function useInfiniteSentinel({
  enabled,
  onLoadMore,
}: InfiniteSentinelOptions) {
  const sentinelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = sentinelRef.current
    if (!element || !enabled) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) onLoadMore()
      },
      { rootMargin: '320px' },
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [enabled, onLoadMore])

  return sentinelRef
}
