import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import {
  addFavorite,
  addReview,
  getCategories,
  getFavoriteStatus,
  getFavorites,
  getPlace,
  getPlaces,
  getReviews,
  removeFavorite,
  submitBusiness,
  type PlaceFilters,
} from './api'
import type { SubmissionInput } from './types'

export const catalogKeys = {
  categories: ['categories'] as const,
  places: (filters: PlaceFilters) => ['places', filters] as const,
  place: (id: string) => ['place', id] as const,
  favorites: ['favorites'] as const,
  favoriteStatus: (id: string) => ['favorite-status', id] as const,
  reviews: (id: string) => ['reviews', id] as const,
}

export function useCategories() {
  return useQuery({
    queryKey: catalogKeys.categories,
    queryFn: ({ signal }) => getCategories(signal),
  })
}

export function usePlaces(filters: PlaceFilters) {
  return useInfiniteQuery({
    queryKey: catalogKeys.places(filters),
    queryFn: ({ pageParam, signal }) =>
      getPlaces(filters, pageParam ?? undefined, signal),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  })
}

export function usePlace(id: string) {
  return useQuery({
    queryKey: catalogKeys.place(id),
    queryFn: ({ signal }) => getPlace(id, signal),
    enabled: Boolean(id),
  })
}

export function useFavorites() {
  return useInfiniteQuery({
    queryKey: catalogKeys.favorites,
    queryFn: ({ pageParam, signal }) => getFavorites(pageParam, signal),
    initialPageParam: 0,
    getNextPageParam: (lastPage) =>
      lastPage.items.length === lastPage.limit
        ? lastPage.offset + lastPage.limit
        : undefined,
  })
}

export function useFavoriteStatus(placeId: string) {
  return useQuery({
    queryKey: catalogKeys.favoriteStatus(placeId),
    queryFn: ({ signal }) => getFavoriteStatus(placeId, signal),
    enabled: Boolean(placeId),
  })
}

export function useToggleFavorite(placeId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (isFavorite: boolean) =>
      isFavorite ? removeFavorite(placeId) : addFavorite(placeId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: catalogKeys.favorites }),
        queryClient.invalidateQueries({
          queryKey: catalogKeys.favoriteStatus(placeId),
        }),
      ])
    },
  })
}

export function useReviews(placeId: string) {
  return useInfiniteQuery({
    queryKey: catalogKeys.reviews(placeId),
    queryFn: ({ pageParam, signal }) => getReviews(placeId, pageParam, signal),
    initialPageParam: 0,
    getNextPageParam: (lastPage) =>
      lastPage.items.length === lastPage.limit
        ? lastPage.offset + lastPage.limit
        : undefined,
    enabled: Boolean(placeId),
  })
}

export function useAddReview(placeId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ rating, comment }: { rating: number; comment: string }) =>
      addReview(placeId, rating, comment),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: catalogKeys.reviews(placeId) }),
        queryClient.invalidateQueries({ queryKey: catalogKeys.place(placeId) }),
        queryClient.invalidateQueries({ queryKey: ['places'] }),
      ])
    },
  })
}

export function useSubmitBusiness() {
  return useMutation({
    mutationFn: (input: SubmissionInput) => submitBusiness(input),
  })
}
