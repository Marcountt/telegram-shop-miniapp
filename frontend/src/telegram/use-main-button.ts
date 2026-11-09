import { useEffect, useRef } from 'react'
import {
  isTMA,
  mountMainButton,
  onMainButtonClick,
  setMainButtonParams,
  unmountMainButton,
} from '@telegram-apps/sdk'

export interface MainButtonOptions {
  text: string
  onClick: () => void
  enabled?: boolean
  loading?: boolean
}

export function useMainButton({
  text,
  onClick,
  enabled = true,
  loading = false,
}: MainButtonOptions): void {
  const onClickRef = useRef(onClick)
  onClickRef.current = onClick

  useEffect(() => {
    if (!isTMA()) {
      return
    }

    if (mountMainButton.isAvailable()) {
      mountMainButton()
    }

    const removeListener = onMainButtonClick.isAvailable()
      ? onMainButtonClick(() => onClickRef.current())
      : undefined

    return () => {
      removeListener?.()
      if (setMainButtonParams.isAvailable()) {
        setMainButtonParams({ isVisible: false, isLoaderVisible: false })
      }
      unmountMainButton()
    }
  }, [])

  useEffect(() => {
    if (!isTMA()) {
      return
    }

    if (setMainButtonParams.isAvailable()) {
      setMainButtonParams({
        text,
        isVisible: true,
        isEnabled: enabled && !loading,
        isLoaderVisible: loading,
      })
    }
  }, [enabled, loading, text])
}
