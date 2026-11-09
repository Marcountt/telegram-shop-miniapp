import { useEffect, useRef } from 'react'
import { useLocation, useNavigate, useNavigationType } from 'react-router'
import {
  hideBackButton,
  isTMA,
  mountBackButton,
  onBackButtonClick,
  showBackButton,
} from '@telegram-apps/sdk'

export function useBackButton(): void {
  const location = useLocation()
  const navigate = useNavigate()
  const navigationType = useNavigationType()
  const routeHistory = useRef<string[]>([location.key])

  useEffect(() => {
    const history = routeHistory.current
    const currentIndex = history.indexOf(location.key)

    if (navigationType === 'PUSH') {
      history.push(location.key)
    } else if (navigationType === 'REPLACE') {
      history[history.length - 1] = location.key
    } else if (currentIndex >= 0) {
      history.splice(currentIndex + 1)
    }
  }, [location.key, navigationType])

  useEffect(() => {
    if (!isTMA()) {
      return
    }

    if (mountBackButton.isAvailable()) {
      mountBackButton()
    }

    const removeListener = onBackButtonClick.isAvailable()
      ? onBackButtonClick(() => {
          if (routeHistory.current.length > 1) {
            navigate(-1)
          }
        })
      : undefined

    return () => removeListener?.()
  }, [navigate])

  useEffect(() => {
    if (!isTMA()) {
      return
    }

    const canGoBack = routeHistory.current.length > 1
    if (canGoBack && showBackButton.isAvailable()) {
      showBackButton()
    } else if (hideBackButton.isAvailable()) {
      hideBackButton()
    }
  }, [location.key])
}
