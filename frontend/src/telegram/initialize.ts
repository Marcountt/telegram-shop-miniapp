import {
  bindThemeParamsCssVars,
  expandViewport,
  init,
  isThemeParamsDark,
  isTMA,
  mountThemeParamsSync,
  miniAppReady,
  setMiniAppBackgroundColor,
  setMiniAppHeaderColor,
  themeParamsState,
} from '@telegram-apps/sdk'

export function syncTelegramColors(): void {
  if (!isTMA()) return

  const background = getComputedStyle(document.documentElement)
    .getPropertyValue('--app-background')
    .trim()

  if (setMiniAppBackgroundColor.isAvailable()) {
    setMiniAppBackgroundColor(background || 'bg_color')
  }
  if (setMiniAppHeaderColor.isAvailable()) {
    if (background && setMiniAppHeaderColor.supports.rgb()) {
      setMiniAppHeaderColor(background)
    } else {
      setMiniAppHeaderColor('bg_color')
    }
  }
}

export function initializeTelegram(): void {
  if (!isTMA()) return

  init()

  if (mountThemeParamsSync.isAvailable()) mountThemeParamsSync()
  if (bindThemeParamsCssVars.isAvailable()) bindThemeParamsCssVars()
  if (expandViewport.isAvailable()) expandViewport()

  const root = document.documentElement
  const applyTheme = (): void => {
    root.dataset.theme = isThemeParamsDark() ? 'dark' : 'light'
    syncTelegramColors()
  }

  applyTheme()
  const unsubscribe = themeParamsState.sub(applyTheme)
  window.addEventListener('pagehide', unsubscribe, { once: true })

  if (miniAppReady.isAvailable()) miniAppReady()
}
