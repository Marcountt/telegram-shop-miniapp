import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { isTMA } from '@telegram-apps/sdk'
import { apiGet, apiRequest } from '../lib/api-client'
import { syncTelegramColors } from '../telegram/initialize'
import type { ProductFavoritePage, StoreCart } from '../store/types'

export type Section = 'men' | 'women'
export type Currency = 'BYN' | 'RUB'

interface Preferences {
  section: Section | 'unisex'
  currency: Currency
}

type PreferencesPatch = Partial<Preferences>

interface PreferencesContextValue {
  section: Section
  setSection: (section: Section) => void
}

interface CurrencyContextValue {
  currency: Currency
  setCurrency: (currency: Currency) => void
}

interface StoreStateContextValue {
  cart: StoreCart | undefined
  cartCount: number
  favoriteIds: Set<string>
  isCartLoading: boolean
  isFavoritesLoading: boolean
  cartError: unknown
  favoriteError: unknown
  addToCart: (variantId: string, quantity?: number) => Promise<void>
  setCartQuantity: (variantId: string, quantity: number) => void
  removeFromCart: (variantId: string) => void
  toggleFavorite: (productId: string) => void
}

const SectionContext = createContext<PreferencesContextValue | null>(null)
const CurrencyContext = createContext<CurrencyContextValue | null>(null)
const StoreStateContext = createContext<StoreStateContextValue | null>(null)

const preferencesKey = ['store', 'preferences'] as const
const favoriteIdsKey = ['store', 'favorite-ids'] as const

function isStoreSection(value: string): value is Section {
  return value === 'men' || value === 'women'
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const telegramAvailable = isTMA()
  const [section, setSectionState] = useState<Section>(() => {
    const saved = window.localStorage.getItem('store-section')
    return saved && isStoreSection(saved) ? saved : 'men'
  })
  const [currency, setCurrencyState] = useState<Currency>(() => {
    return window.localStorage.getItem('store-currency') === 'RUB' ? 'RUB' : 'BYN'
  })
  const [preferencesDirty, setPreferencesDirty] = useState(false)
  const cartKey = ['store', 'cart', currency] as const
  const favoritesKey = ['store', 'favorites', currency] as const

  const preferencesQuery = useQuery({
    queryKey: preferencesKey,
    queryFn: ({ signal }) => apiGet<Preferences>('/api/me/preferences', signal),
    enabled: telegramAvailable,
  })

  useEffect(() => {
    const preferences = preferencesQuery.data
    if (!preferences || preferencesDirty) return
    if (isStoreSection(preferences.section)) {
      setSectionState(preferences.section)
      window.localStorage.setItem('store-section', preferences.section)
    }
    setCurrencyState(preferences.currency)
    window.localStorage.setItem('store-currency', preferences.currency)
  }, [preferencesDirty, preferencesQuery.data])

  const savePreferences = useMutation({
    mutationFn: (preferences: PreferencesPatch) =>
      apiRequest<Preferences>('/api/me/preferences', {
        method: 'PUT',
        body: JSON.stringify(preferences),
      }),
    onMutate: async (preferences) => {
      await queryClient.cancelQueries({ queryKey: preferencesKey })
      const previous = queryClient.getQueryData<Preferences>(preferencesKey)
      if (previous) {
        queryClient.setQueryData<Preferences>(preferencesKey, {
          ...previous,
          ...preferences,
        })
      }
      return { previous }
    },
    onError: (_error, _preferences, context) => {
      if (context?.previous) queryClient.setQueryData(preferencesKey, context.previous)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: preferencesKey }),
  })

  const setSection = (nextSection: Section) => {
    setPreferencesDirty(true)
    setSectionState(nextSection)
    window.localStorage.setItem('store-section', nextSection)
    if (telegramAvailable) {
      savePreferences.mutate({ section: nextSection })
    }
  }

  const setCurrency = (nextCurrency: Currency) => {
    setPreferencesDirty(true)
    setCurrencyState(nextCurrency)
    window.localStorage.setItem('store-currency', nextCurrency)
    if (telegramAvailable) {
      savePreferences.mutate({ currency: nextCurrency })
    }
  }

  const cartQuery = useQuery({
    queryKey: cartKey,
    queryFn: ({ signal }) => apiGet<StoreCart>(`/api/cart?currency=${currency}`, signal),
    enabled: telegramAvailable,
  })
  const favoritesQuery = useQuery({
    queryKey: favoritesKey,
    queryFn: ({ signal }) =>
      apiGet<ProductFavoritePage>(
        `/api/store/favorites?currency=${currency}&page=1&page_size=100`,
        signal,
      ),
    enabled: telegramAvailable,
  })

  useEffect(() => {
    queryClient.setQueryData(
      favoriteIdsKey,
      new Set((favoritesQuery.data?.items ?? []).map((item) => item.id)),
    )
  }, [favoritesQuery.data, queryClient])

  const addCartMutation = useMutation({
    mutationFn: ({ variantId, quantity }: { variantId: string; quantity: number }) =>
      apiRequest<StoreCart>(`/api/cart/items?currency=${currency}`, {
        method: 'POST',
        body: JSON.stringify({ variant_id: variantId, quantity }),
      }),
    onMutate: async ({ quantity }) => {
      await queryClient.cancelQueries({ queryKey: cartKey })
      const previous = queryClient.getQueryData<StoreCart>(cartKey)
      if (previous) {
        queryClient.setQueryData<StoreCart>(cartKey, {
          ...previous,
          item_count: previous.item_count + quantity,
        })
      }
      return { previous }
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(cartKey, context.previous)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: cartKey }),
  })

  const quantityMutation = useMutation({
    mutationFn: ({ variantId, quantity }: { variantId: string; quantity: number }) =>
      apiRequest<StoreCart>(
        `/api/cart/items/${encodeURIComponent(variantId)}?currency=${currency}`,
        { method: 'PATCH', body: JSON.stringify({ quantity }) },
      ),
    onMutate: async ({ variantId, quantity }) => {
      await queryClient.cancelQueries({ queryKey: cartKey })
      const previous = queryClient.getQueryData<StoreCart>(cartKey)
      if (previous) {
        const oldQuantity =
          previous.items.find((item) => item.variant_id === variantId)?.quantity ?? 0
        queryClient.setQueryData<StoreCart>(cartKey, {
          ...previous,
          item_count: Math.max(0, previous.item_count + quantity - oldQuantity),
          items: previous.items.map((item) =>
            item.variant_id === variantId ? { ...item, quantity } : item,
          ),
        })
      }
      return { previous }
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(cartKey, context.previous)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: cartKey }),
  })

  const removeCartMutation = useMutation({
    mutationFn: (variantId: string) =>
      apiRequest<StoreCart>(
        `/api/cart/items/${encodeURIComponent(variantId)}?currency=${currency}`,
        { method: 'DELETE' },
      ),
    onMutate: async (variantId) => {
      await queryClient.cancelQueries({ queryKey: cartKey })
      const previous = queryClient.getQueryData<StoreCart>(cartKey)
      const removed =
        previous?.items.find((item) => item.variant_id === variantId)?.quantity ?? 0
      if (previous) {
        queryClient.setQueryData<StoreCart>(cartKey, {
          ...previous,
          item_count: Math.max(0, previous.item_count - removed),
          items: previous.items.filter((item) => item.variant_id !== variantId),
        })
      }
      return { previous }
    },
    onError: (_error, _variantId, context) => {
      if (context?.previous) queryClient.setQueryData(cartKey, context.previous)
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: cartKey }),
  })

  const favoriteMutation = useMutation({
    mutationFn: ({ productId, active }: { productId: string; active: boolean }) =>
      apiRequest(
        `/api/store/favorites/${encodeURIComponent(productId)}`,
        { method: active ? 'PUT' : 'DELETE' },
      ),
    onMutate: async ({ productId, active }) => {
      await queryClient.cancelQueries({ queryKey: favoriteIdsKey })
      const previous =
        queryClient.getQueryData<Set<string>>(favoriteIdsKey) ?? new Set<string>()
      const next = new Set(previous)
      if (active) next.add(productId)
      else next.delete(productId)
      queryClient.setQueryData(favoriteIdsKey, next)
      return { previous }
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(favoriteIdsKey, context.previous)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: favoritesKey })
      queryClient.invalidateQueries({ queryKey: favoriteIdsKey })
    },
  })
  const favoriteIdsQuery = useQuery({
    queryKey: favoriteIdsKey,
    queryFn: async () => new Set<string>(),
    enabled: false,
    initialData: () => new Set<string>(),
  })

  const sectionValue = useMemo(
    () => ({ section, setSection }),
    [section],
  )
  const currencyValue = useMemo(
    () => ({ currency, setCurrency }),
    [currency, section],
  )
  const storeStateValue = useMemo<StoreStateContextValue>(
    () => ({
      cart: cartQuery.data,
      cartCount: cartQuery.data?.item_count ?? 0,
      favoriteIds: favoriteIdsQuery.data,
      isCartLoading: cartQuery.isLoading,
      isFavoritesLoading: favoritesQuery.isLoading,
      cartError:
        addCartMutation.error ??
        quantityMutation.error ??
        removeCartMutation.error ??
        cartQuery.error,
      favoriteError: favoriteMutation.error,
      addToCart: (variantId, quantity = 1) =>
        addCartMutation.mutateAsync({ variantId, quantity }).then(() => undefined),
      setCartQuantity: (variantId, quantity) =>
        quantityMutation.mutate({ variantId, quantity }),
      removeFromCart: (variantId) => removeCartMutation.mutate(variantId),
      toggleFavorite: (productId) => {
        const current =
          queryClient.getQueryData<Set<string>>(favoriteIdsKey) ?? new Set<string>()
        favoriteMutation.mutate({ productId, active: !current.has(productId) })
      },
    }),
    [
      addCartMutation,
      cartQuery.data,
      cartQuery.error,
      cartQuery.isLoading,
      favoriteMutation,
      favoritesQuery.isLoading,
      favoriteIdsQuery.data,
      queryClient,
      quantityMutation,
      removeCartMutation,
    ],
  )

  useEffect(() => {
    document.documentElement.dataset.section = section
    syncTelegramColors()
  }, [section])

  return (
    <SectionContext.Provider value={sectionValue}>
      <CurrencyContext.Provider value={currencyValue}>
        <StoreStateContext.Provider value={storeStateValue}>
          {children}
        </StoreStateContext.Provider>
      </CurrencyContext.Provider>
    </SectionContext.Provider>
  )
}

export function useSection(): PreferencesContextValue {
  const value = useContext(SectionContext)
  if (!value) throw new Error('useSection должен использоваться внутри StoreProvider.')
  return value
}

export function useCurrency(): CurrencyContextValue {
  const value = useContext(CurrencyContext)
  if (!value) throw new Error('useCurrency должен использоваться внутри StoreProvider.')
  return value
}

export function useStoreState(): StoreStateContextValue {
  const value = useContext(StoreStateContext)
  if (!value) throw new Error('useStoreState должен использоваться внутри StoreProvider.')
  return value
}
