import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type MouseEvent, type TouchEvent } from 'react'
import {
  useInfiniteQuery,
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useMotionValueEvent,
  useReducedMotion,
  useSpring,
} from 'framer-motion'
import { isTMA, openTelegramLink } from '@telegram-apps/sdk'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router'
import { useCurrency, useSection, useStoreState } from '../app/store-context'
import {
  BottomSheet,
  Drawer,
  EmptyState,
  ProductCard,
  QuantityStepper,
  SegmentedControl,
  SizeChip,
} from '../components/ui'
import { ApiError } from '../lib/api-client'
import { useInfiniteSentinel } from '../hooks/use-infinite-sentinel'
import { triggerHaptic, triggerSelectionHaptic } from '../telegram/haptics'
import { motionDuration, motionEase } from '../lib/motion'
import {
  createOrder,
  getCategories,
  getCustomerProfile,
  getFavorites,
  getOrder,
  getOrders,
  getProduct,
  getProducts,
  getPublicSettings,
  getSizes,
  storeKeys,
  type CatalogFilters,
} from './api'
import type {
  CheckoutPayload,
  DeliveryMethod,
  OrderCreated,
  OrderDetail,
  ProductCardData,
  ProductDetailData,
  StoreCategory,
  StoreCurrency,
} from './types'

const OrderSuccessAnimation = lazy(() =>
  import('./OrderSuccessAnimation').then((module) => ({ default: module.OrderSuccessAnimation })),
)

const categoriesFilter = [
  'Верхняя одежда',
  'Кофты / Свитера',
  'Футболки / Поло',
  'Рубашки',
  'Шорты',
  'Штаны',
  'Аксессуары',
]

const sortOptions = [
  { value: 'newest', label: 'СНАЧАЛА НОВЫЕ', short: 'СЕГОДНЯ' },
  { value: 'price_desc', label: 'СНАЧАЛА ДОРОЖЕ', short: 'ДОРОЖЕ' },
  { value: 'price_asc', label: 'СНАЧАЛА ДЕШЕВЛЕ', short: 'ДЕШЕВЛЕ' },
] as const

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Не удалось загрузить данные. Попробуйте ещё раз.'
}

function TelegramRequired() {
  return (
    <EmptyState
      title="ОТКРОЙТЕ В TELEGRAM"
      description="Каталог и покупки доступны в Telegram Mini App."
    />
  )
}

function LoadingGrid() {
  return (
    <div aria-busy="true" className="store-product-grid">
      {Array.from({ length: 4 }, (_, index) => (
        <div className="product-card store-product-skeleton" key={index}>
          <div className="store-product-skeleton__image" />
          <div className="store-product-skeleton__line" />
          <div className="store-product-skeleton__line store-product-skeleton__line--short" />
        </div>
      ))}
    </div>
  )
}

function AnimatedTotal({ value, currency }: { value: number | string; currency: StoreCurrency }) {
  const reduceMotion = useReducedMotion()
  const amount = useMotionValue(Number(value))
  const spring = useSpring(amount, reduceMotion ? { stiffness: 1000, damping: 100 } : {
    stiffness: 150,
    damping: 24,
  })
  const [displayValue, setDisplayValue] = useState(formatCurrency(value, currency))

  useEffect(() => {
    amount.set(Number(value))
    if (reduceMotion) setDisplayValue(formatCurrency(value, currency))
  }, [amount, currency, reduceMotion, value])

  useMotionValueEvent(spring, 'change', (latest) => {
    if (!reduceMotion) setDisplayValue(formatCurrency(latest, currency))
  })

  return <motion.strong>{displayValue}</motion.strong>
}

function ErrorState({ error, retry }: { error: unknown; retry: () => void }) {
  return (
    <EmptyState
      action={
        <button className="ui-button ui-button--secondary" onClick={retry} type="button">
          ПОВТОРИТЬ
        </button>
      }
      description={errorText(error)}
      title="НЕ УДАЛОСЬ ЗАГРУЗИТЬ"
    />
  )
}

function categoryForLabel(
  label: string,
  categories: StoreCategory[],
): StoreCategory | undefined {
  const keywords: Record<string, string[]> = {
    'Верхняя одежда': ['верх', 'куртк', 'пальто'],
    'Кофты / Свитера': ['кофт', 'свит', 'худи', 'толстов'],
    'Футболки / Поло': ['футбол', 'поло'],
    Рубашки: ['рубаш'],
    Шорты: ['шорт'],
    Штаны: ['штан', 'брюк'],
    Аксессуары: ['аксесс'],
  }
  const terms = keywords[label] ?? [label.toLocaleLowerCase('ru-RU')]
  return categories.find((category) => {
    const text = `${category.name} ${category.slug}`.toLocaleLowerCase('ru-RU')
    return terms.some((term) => text.includes(term))
  })
}

function productSizeBadge(product: ProductCardData): string | undefined {
  if (product.sizes.length === 0) return undefined
  if (product.sizes.length === 1) return product.sizes[0]
  return `${product.sizes[0]}-${product.sizes[product.sizes.length - 1]}`
}

function deliveryLabel(method: DeliveryMethod): string {
  const labels: Record<string, string> = {
    courier: 'Курьер',
    belpochta: 'Белпочта',
    europochta: 'Европочта',
    cdek: 'СДЭК',
  }
  return labels[method.code.toLowerCase()] ?? method.name
}

export function EntryScreen() {
  const navigate = useNavigate()
  const { setSection } = useSection()
  const reduceMotion = useReducedMotion()
  const [selected, setSelected] = useState<'men' | 'women' | null>(null)
  const [circle, setCircle] = useState<{ x: number; y: number; scale: number } | null>(null)

  const choose = (section: 'men' | 'women', event: MouseEvent<HTMLButtonElement>) => {
    triggerHaptic()
    setSelected(section)
    const bounds = event.currentTarget.getBoundingClientRect()
    const x = bounds.left + bounds.width / 2
    const y = bounds.top + bounds.height / 2
    const reach = Math.max(
      Math.hypot(x, y),
      Math.hypot(window.innerWidth - x, y),
      Math.hypot(x, window.innerHeight - y),
      Math.hypot(window.innerWidth - x, window.innerHeight - y),
    )
    setCircle({ x, y, scale: reach / 6 })
    window.localStorage.setItem('store-entry-selected', 'true')
    setSection(section)
  }

  return (
    <section className={`entry-screen${selected ? ' entry-screen--chosen' : ''}`}>
      <p aria-label="BRAND GRODNO" className="eyebrow entry-screen__logo">
        {'BRAND GRODNO'.split('').map((letter, index) => (
          <motion.span
            aria-hidden="true"
            animate={{ opacity: 1, y: 0 }}
            initial={{ opacity: 0, y: reduceMotion ? 0 : 8 }}
            key={`${letter}-${index}`}
            transition={{ delay: reduceMotion ? 0 : index * motionDuration.entryReveal, duration: motionDuration.fade }}
          >
            {letter === ' ' ? '\u00a0' : letter}
          </motion.span>
        ))}
      </p>
      <h1>ТВОЙ СТИЛЬ.<br />ТВОЙ ВЫБОР.</h1>
      <p className="entry-screen__intro">Выберите коллекцию, чтобы начать покупки.</p>
      <div className="entry-screen__cards">
        {([
          { key: 'women', title: 'Женское', number: '01' },
          { key: 'men', title: 'Мужское', number: '02' },
        ] as const).map((item, index) => (
          <motion.button
            animate={{ opacity: selected && selected !== item.key ? 0 : 1, y: 0 }}
            className={`entry-card entry-card--${item.key}`}
            initial={{ opacity: 0, y: reduceMotion ? 0 : 22 }}
            key={item.key}
            onClick={(event) => choose(item.key, event)}
            transition={{
              opacity: { duration: motionDuration.fade, delay: reduceMotion ? 0 : index * motionDuration.stagger },
              y: { duration: motionDuration.entry, delay: reduceMotion ? 0 : index * motionDuration.stagger, ease: motionEase.standard },
            }}
            whileTap={reduceMotion ? { opacity: 0.82 } : { scale: 0.97 }}
          >
            <span className="entry-card__number">{item.number}</span>
            <span className="entry-card__title">{item.title}</span>
            <span className="entry-card__arrow" aria-hidden="true">↗</span>
          </motion.button>
        ))}
      </div>
      <AnimatePresence>
        {circle && (
          <motion.span
            aria-hidden="true"
            animate={{ opacity: 1, scale: reduceMotion ? 1 : circle.scale }}
            className={`entry-transition-circle entry-transition-circle--${selected}`}
            initial={{ opacity: 0.7, scale: 0 }}
            onAnimationComplete={() => navigate('/shop/clothing', { replace: true })}
            style={{ left: circle.x, top: circle.y, x: '-50%', y: '-50%' }}
            transition={{ duration: reduceMotion ? motionDuration.fade : motionDuration.entry, ease: motionEase.standard }}
          />
        )}
      </AnimatePresence>
    </section>
  )
}

export function CatalogScreen({ group }: { group: 'clothing' | 'shoes' }) {
  const { section, setSection } = useSection()
  const { currency, setCurrency } = useCurrency()
  const {
    favoriteIds,
    toggleFavorite,
    addToCart,
    cartError,
    favoriteError,
  } = useStoreState()
  const reduceMotion = useReducedMotion()
  const previousSection = useRef(section)
  const contentDirection = previousSection.current === section
    ? 1
    : section === 'men' ? 1 : -1
  const [searchParams] = useSearchParams()
  const [filterOpen, setFilterOpen] = useState(false)
  const [sortOpen, setSortOpen] = useState(false)
  const [chooseProduct, setChooseProduct] = useState<ProductCardData | null>(null)
  const [chosenSize, setChosenSize] = useState<string | null>(null)
  const [categoryId, setCategoryId] = useState('')
  const [size, setSize] = useState('')
  const [minPrice, setMinPrice] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [onSale, setOnSale] = useState(false)
  const [sort, setSort] = useState<CatalogFilters['sort']>('newest')
  const [draftCategory, setDraftCategory] = useState('')
  const [draftSize, setDraftSize] = useState('')
  const [draftMinPrice, setDraftMinPrice] = useState('')
  const [draftMaxPrice, setDraftMaxPrice] = useState('')
  const [draftSale, setDraftSale] = useState(false)
  const [catalogActionError, setCatalogActionError] = useState('')
  const queryClient = useQueryClient()
  const search = searchParams.get('q') ?? ''
  useEffect(() => {
    previousSection.current = section
  }, [section])
  const filters = useMemo<CatalogFilters>(
    () => ({
      group,
      section,
      currency,
      search,
      categoryId,
      size,
      minPrice,
      maxPrice,
      onSale,
      sort,
    }),
    [categoryId, currency, group, maxPrice, minPrice, onSale, search, section, size, sort],
  )
  const productsQuery = useInfiniteQuery({
    queryKey: storeKeys.products(filters),
    queryFn: ({ pageParam, signal }) => getProducts(filters, pageParam, signal),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined,
    enabled: isTMA(),
  })
  const categoriesQuery = useQuery({
    queryKey: storeKeys.categories(group),
    queryFn: ({ signal }) => getCategories(group, signal),
    enabled: isTMA(),
  })
  const sizesQuery = useQuery({
    queryKey: storeKeys.sizes(group),
    queryFn: ({ signal }) => getSizes(group, signal),
    enabled: isTMA(),
  })
  const categories = categoriesQuery.data ?? []
  const sizes = sizesQuery.data ?? []
  const products = productsQuery.data?.pages.flatMap((page) => page.items) ?? []
  const activeFilterCount = Number(Boolean(categoryId)) + Number(Boolean(size)) +
    Number(Boolean(minPrice || maxPrice)) + Number(onSale)
  const draftFilterCount = Number(Boolean(draftCategory)) + Number(Boolean(draftSize)) +
    Number(Boolean(draftMinPrice || draftMaxPrice)) + Number(draftSale)
  const sortLabel = sortOptions.find((option) => option.value === sort)?.short ?? 'СЕГОДНЯ'
  const loadNextPage = useCallback(() => {
    if (productsQuery.hasNextPage && !productsQuery.isFetchingNextPage) {
      void productsQuery.fetchNextPage()
    }
  }, [productsQuery.fetchNextPage, productsQuery.hasNextPage, productsQuery.isFetchingNextPage])
  const sentinelRef = useInfiniteSentinel({
    enabled: Boolean(productsQuery.hasNextPage && !productsQuery.isFetchingNextPage),
    onLoadMore: loadNextPage,
  })

  const openFilters = () => {
    setDraftCategory(categoryId)
    setDraftSize(size)
    setDraftMinPrice(minPrice)
    setDraftMaxPrice(maxPrice)
    setDraftSale(onSale)
    setFilterOpen(true)
  }
  const resetFilters = () => {
    setCategoryId('')
    setSize('')
    setMinPrice('')
    setMaxPrice('')
    setOnSale(false)
  }
  const resetDraftFilters = () => {
    setDraftCategory('')
    setDraftSize('')
    setDraftMinPrice('')
    setDraftMaxPrice('')
    setDraftSale(false)
  }
  const chooseProductForCart = async (item: ProductCardData) => {
    setCatalogActionError('')
    try {
      const detail = await queryClient.fetchQuery({
        queryKey: storeKeys.product(item.id, currency),
        queryFn: ({ signal }) => getProduct(item.id, currency, signal),
      })
      const available = detail.variants.filter((variant) => variant.stock > 0)
      const availableSizes = [...new Set(available.map((variant) => variant.size))]
      if (availableSizes.length === 1 && available.length === 1) {
        await addToCart(available[0].id)
        return
      }
      if (available.length === 0) {
        setCatalogActionError('Сейчас нет доступных размеров этого товара.')
        return
      }
      setChooseProduct(item)
      setChosenSize(null)
    } catch (error) {
      setCatalogActionError(errorText(error))
    }
  }
  const addChosenVariant = async () => {
    if (!chooseProduct || !chosenSize) return
    const detail = queryClient.getQueryData<ProductDetailData>(
      storeKeys.product(chooseProduct.id, currency),
    )
    const variant = detail?.variants.find(
      (item) => item.size === chosenSize && item.stock > 0,
    )
    if (variant) {
      try {
        await addToCart(variant.id)
        setChooseProduct(null)
        setChosenSize(null)
      } catch (error) {
        setCatalogActionError(errorText(error))
      }
    }
  }

  if (!isTMA()) return <TelegramRequired />

  return (
    <div className="catalog-screen">
      <div className="catalog-section-switch" role="group" aria-label="Раздел">
        <motion.span
          className="catalog-section-switch__indicator"
          layoutId="catalog-section-indicator"
          style={{ left: section === 'men' ? '50%' : '0%' }}
          transition={reduceMotion ? { duration: motionDuration.fade } : motionEase.spring}
        />
        <button className={section === 'women' ? 'is-active' : ''} onClick={() => setSection('women')} type="button">
          ЖЕНСКОЕ
        </button>
        <button className={section === 'men' ? 'is-active' : ''} onClick={() => setSection('men')} type="button">
          МУЖСКОЕ
        </button>
      </div>

      <div className="catalog-toolbar">
        <button className="catalog-toolbar__button" onClick={openFilters} type="button">
          ФИЛЬТРЫ +{activeFilterCount > 0 && <span>{activeFilterCount}</span>}
        </button>
        <button className="catalog-toolbar__button" onClick={() => setSortOpen(true)} type="button">
          {sortLabel} <span aria-hidden="true">⌄</span>
        </button>
      </div>

      <div className="catalog-currency">
        <SegmentedControl
          label="Валюта"
          onChange={setCurrency}
          options={[
            { value: 'BYN', label: 'BYN' },
            { value: 'RUB', label: 'RUB' },
          ]}
          value={currency}
        />
      </div>

      {productsQuery.isLoading && <LoadingGrid />}
      {productsQuery.isError && <ErrorState error={productsQuery.error} retry={() => productsQuery.refetch()} />}
      {!productsQuery.isLoading && !productsQuery.isError && products.length === 0 && (
        <EmptyState
          action={activeFilterCount > 0 ? (
            <button className="ui-button ui-button--secondary" onClick={resetFilters} type="button">
              СБРОСИТЬ ФИЛЬТРЫ
            </button>
          ) : undefined}
          description="Попробуйте изменить фильтры или загляните позже."
          title="ТОВАРЫ НЕ НАЙДЕНЫ"
        />
      )}
      {products.length > 0 && (
        <AnimatePresence initial={false} mode="wait">
          <motion.div
            animate="visible"
            className="store-product-grid"
            initial="hidden"
            key={`${section}-${group}-${search}-${categoryId}-${size}-${minPrice}-${maxPrice}-${onSale}-${sort}`}
            transition={{
              delayChildren: reduceMotion ? 0 : motionDuration.fade / 2,
              staggerChildren: reduceMotion ? 0 : motionDuration.gridStagger,
            }}
            variants={{
              hidden: { opacity: 0, x: reduceMotion ? 0 : contentDirection * -10 },
              visible: { opacity: 1, x: 0 },
            }}
          >
            {products.map((product) => (
              <ProductCard
                isFavorite={favoriteIds.has(product.id)}
                key={product.id}
                onAdd={(item) => void chooseProductForCart(item)}
                onFavorite={toggleFavorite}
                product={product}
                sizeBadge={productSizeBadge(product)}
              />
            ))}
          </motion.div>
        </AnimatePresence>
      )}
      <div aria-hidden="true" className="store-infinite-sentinel" ref={sentinelRef} />
      {productsQuery.isFetchingNextPage && <LoadingGrid />}
      {catalogActionError && <p className="store-inline-error" role="alert">{catalogActionError}</p>}
      {cartError != null && (
        <p className="store-inline-error" role="alert">{errorText(cartError)}</p>
      )}
      {favoriteError != null && (
        <p className="store-inline-error" role="alert">{errorText(favoriteError)}</p>
      )}
      {productsQuery.hasNextPage && (
        <button
          className="catalog-load-more"
          disabled={productsQuery.isFetchingNextPage}
          onClick={loadNextPage}
          type="button"
        >
          {productsQuery.isFetchingNextPage ? 'ЗАГРУЖАЕМ…' : 'ПОКАЗАТЬ ЕЩЁ'}
        </button>
      )}

      <Drawer open={filterOpen} onClose={() => setFilterOpen(false)} title="ФИЛЬТР">
        <div className="store-drawer__content filter-drawer-content">
          <section className="store-filter-section">
            <h2>КАТЕГОРИЯ</h2>
            <button
              className={`store-category-option${draftCategory ? '' : ' is-selected'}`}
              onClick={() => setDraftCategory('')}
              type="button"
            >
              <span>Все товары</span>{!draftCategory && <span>✓</span>}
            </button>
            {categoriesFilter.map((label) => {
              const category = categoryForLabel(label, categories)
              const selected = category?.id === draftCategory
              return (
                <button
                  className={`store-category-option${selected ? ' is-selected' : ''}${category ? '' : ' is-unavailable'}`}
                  disabled={!category}
                  key={label}
                  onClick={() => setDraftCategory(category?.id ?? '')}
                  type="button"
                >
                  <span>{label}</span>{selected && <span>✓</span>}
                </button>
              )
            })}
            <button
              className={`store-category-option${draftSale ? ' is-selected' : ''}`}
              onClick={() => setDraftSale((value) => !value)}
              type="button"
            >
              <span>Товары со скидкой</span>{draftSale && <span>✓</span>}
            </button>
          </section>

          <section className="store-filter-section">
            <h2>РАЗМЕР</h2>
            <div className="store-chip-row">
              <SizeChip onClick={() => setDraftSize('')} selected={!draftSize} size="ВСЕ" />
              {sizesQuery.isLoading && <span className="eyebrow">ЗАГРУЗКА…</span>}
              {sizes.map((item) => (
                <SizeChip
                  key={item.id}
                  onClick={() => setDraftSize(item.value === draftSize ? '' : item.value)}
                  selected={draftSize === item.value}
                  size={item.value}
                />
              ))}
            </div>
            {sizesQuery.isError && <p className="store-inline-error">{errorText(sizesQuery.error)}</p>}
          </section>

          <section className="store-filter-section">
            <h2>ЦЕНА · {currency}</h2>
            <div className="store-price-inputs">
              <label>
                <span>ОТ</span>
                <input
                  inputMode="decimal"
                  min="0"
                  onChange={(event) => setDraftMinPrice(event.target.value)}
                  placeholder="БЕЗ ОГРАНИЧЕНИЯ"
                  type="number"
                  value={draftMinPrice}
                />
              </label>
              <label>
                <span>ДО</span>
                <input
                  inputMode="decimal"
                  min="0"
                  onChange={(event) => setDraftMaxPrice(event.target.value)}
                  placeholder="БЕЗ ОГРАНИЧЕНИЯ"
                  type="number"
                  value={draftMaxPrice}
                />
              </label>
            </div>
          </section>

          <div className="store-filter-footer">
            <p>{draftFilterCount ? `ВЫБРАНО ФИЛЬТРОВ: ${draftFilterCount}` : 'ФИЛЬТРЫ НЕ ВЫБРАНЫ'}</p>
            <div>
              <button className="ui-button ui-button--secondary" onClick={resetDraftFilters} type="button">СБРОСИТЬ</button>
              <button
                className="ui-button ui-button--primary"
                onClick={() => {
                  setCategoryId(draftCategory)
                  setSize(draftSize)
                  setMinPrice(draftMinPrice)
                  setMaxPrice(draftMaxPrice)
                  setOnSale(draftSale)
                  setFilterOpen(false)
                }}
                type="button"
              >
                ПОКАЗАТЬ
              </button>
            </div>
          </div>
        </div>
      </Drawer>

      <Drawer open={sortOpen} onClose={() => setSortOpen(false)} side="right" title="СОРТИРОВКА">
        <div className="store-sort-options">
          {sortOptions.map((option) => (
            <button
              className={sort === option.value ? 'is-selected' : ''}
              key={option.value}
              onClick={() => {
                setSort(option.value)
                setSortOpen(false)
                triggerSelectionHaptic()
              }}
              type="button"
            >
              {option.label}{sort === option.value && <span>✓</span>}
            </button>
          ))}
        </div>
      </Drawer>

      <ProductSizeSheet
        currency={currency}
        onAdd={addChosenVariant}
        onClose={() => setChooseProduct(null)}
        product={chooseProduct}
        selectedSize={chosenSize}
        setSelectedSize={setChosenSize}
      />
    </div>
  )
}

function ProductSizeSheet({
  product,
  currency,
  selectedSize,
  setSelectedSize,
  onAdd,
  onClose,
}: {
  product: ProductCardData | null
  currency: StoreCurrency
  selectedSize: string | null
  setSelectedSize: (size: string | null) => void
  onAdd: () => void
  onClose: () => void
}) {
  const query = useQuery({
    queryKey: storeKeys.product(product?.id ?? '', currency),
    queryFn: ({ signal }) => getProduct(product?.id ?? '', currency, signal),
    enabled: Boolean(product && isTMA()),
  })
  const variants = query.data?.variants ?? []
  const availableSizes = [...new Set(variants.map((variant) => variant.size))]
  return (
    <BottomSheet open={Boolean(product)} onClose={onClose} title="ВЫБЕРИТЕ РАЗМЕР">
      {query.isLoading && <p className="eyebrow">ЗАГРУЗКА РАЗМЕРОВ…</p>}
      {query.isError && <p className="store-inline-error">{errorText(query.error)}</p>}
      {query.data && (
        <>
          <p className="store-sheet-product-title">{query.data.title}</p>
          <div className="store-chip-row">
            {availableSizes.map((itemSize) => (
              <SizeChip
                disabled={!variants.some((variant) => variant.size === itemSize && variant.stock > 0)}
                key={itemSize}
                onClick={() => setSelectedSize(itemSize)}
                selected={selectedSize === itemSize}
                size={itemSize}
              />
            ))}
          </div>
          <button
            className="ui-button ui-button--primary store-sheet-add"
            disabled={!selectedSize || query.isLoading}
            onClick={onAdd}
            type="button"
          >
            ДОБАВИТЬ В КОРЗИНУ
          </button>
        </>
      )}
    </BottomSheet>
  )
}

export function ProductScreen() {
  const { productId = '' } = useParams()
  const { currency } = useCurrency()
  const { favoriteIds, toggleFavorite, addToCart } = useStoreState()
  const { favoriteError } = useStoreState()
  const [selectedVariantId, setSelectedVariantId] = useState('')
  const [imageIndex, setImageIndex] = useState(0)
  const [imageDirection, setImageDirection] = useState(1)
  const [toast, setToast] = useState('')
  const [added, setAdded] = useState(false)
  const [flyingPhoto, setFlyingPhoto] = useState<{
    src: string
    fromX: number
    fromY: number
    toX: number
    toY: number
  } | null>(null)
  const touchStart = useRef(0)
  const reduceMotion = useReducedMotion()
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: storeKeys.product(productId, currency),
    queryFn: ({ signal }) => getProduct(productId, currency, signal),
    enabled: isTMA() && Boolean(productId),
  })
  const product = query.data
  const selectedVariant = product?.variants.find((variant) => variant.id === selectedVariantId)
  const currentImage = product?.images[imageIndex]?.url

  const handleTouchStart = (event: TouchEvent<HTMLElement>) => {
    touchStart.current = event.touches[0]?.clientX ?? 0
  }
  const handleTouchEnd = (event: TouchEvent<HTMLElement>) => {
    const delta = (event.changedTouches[0]?.clientX ?? touchStart.current) - touchStart.current
    if (Math.abs(delta) < 40 || !product?.images.length) return
    setImageDirection(delta < 0 ? 1 : -1)
    setImageIndex((index) =>
      delta < 0
        ? (index + 1) % product.images.length
        : (index - 1 + product.images.length) % product.images.length,
    )
  }

  if (!isTMA()) return <TelegramRequired />
  if (query.isLoading) return <LoadingGrid />
  if (query.isError) return <ErrorState error={query.error} retry={() => query.refetch()} />
  if (!product) return <EmptyState title="ТОВАР НЕ НАЙДЕН" />

  const discounted =
    product.original_price != null && Number(product.original_price) > Number(product.price)
  const addProduct = async () => {
    if (!selectedVariant || selectedVariant.stock === 0) return
    try {
      await addToCart(selectedVariant.id)
      triggerHaptic()
      setToast('ДОБАВЛЕНО В КОРЗИНУ')
      setAdded(true)
      window.setTimeout(() => setAdded(false), 1500)
      const gallery = document.querySelector<HTMLElement>('.product-detail__gallery')
      const cartTarget = document.querySelector<HTMLElement>('[data-cart-target]')
      if (currentImage && gallery && cartTarget) {
        const from = gallery.getBoundingClientRect()
        const to = cartTarget.getBoundingClientRect()
        setFlyingPhoto({
          src: currentImage,
          fromX: from.left + from.width / 2,
          fromY: from.top + from.height / 2,
          toX: to.left + to.width / 2,
          toY: to.top + to.height / 2,
        })
      }
      window.setTimeout(() => setToast(''), 1800)
      void queryClient.invalidateQueries({ queryKey: ['store', 'cart'] })
    } catch (error) {
      setToast(errorText(error))
    }
  }

  return (
    <article className="product-detail">
      <section
        aria-label="Фотографии товара"
        className="product-detail__gallery"
        onTouchEnd={handleTouchEnd}
        onTouchStart={handleTouchStart}
      >
        <AnimatePresence initial={false} mode="wait">
          {currentImage ? (
            <motion.img
              alt={product.title}
              animate={{ opacity: 1, x: 0 }}
              initial={{ opacity: 0, x: reduceMotion ? 0 : imageDirection * 18 }}
              key={currentImage}
              layoutId={imageIndex === 0 ? `product-photo-${product.id}-0` : undefined}
              src={currentImage}
              exit={{ opacity: 0, x: reduceMotion ? 0 : imageDirection * -18 }}
              transition={reduceMotion ? { duration: motionDuration.fade } : motionEase.sheetSpring}
            />
          ) : (
            <motion.div
              animate={{ opacity: 1 }}
              className="product-detail__image-placeholder"
              exit={{ opacity: 0 }}
              initial={{ opacity: 0 }}
            />
          )}
        </AnimatePresence>
        {product.images.length > 1 && (
          <div aria-label={`Фото ${imageIndex + 1} из ${product.images.length}`} className="product-detail__dots">
            {product.images.map((image, index) => (
              <button
                aria-label={`Показать фото ${index + 1}`}
                aria-pressed={index === imageIndex}
                className={index === imageIndex ? 'is-active' : ''}
                key={`${image.url}-${index}`}
                onClick={() => {
                  setImageDirection(index > imageIndex ? 1 : -1)
                  setImageIndex(index)
                }}
                type="button"
              >
                {index === imageIndex && <motion.span layoutId="product-gallery-active-dot" />}
              </button>
            ))}
          </div>
        )}
        {product.images.length > 1 && (
          <div aria-hidden="true" className="product-detail__progress">
            {product.images.map((image, index) => (
              <span className={index === imageIndex ? 'is-active' : ''} key={`${image.url}-progress-${index}`}>
                {index === imageIndex && <motion.i layoutId="product-gallery-progress" />}
              </span>
            ))}
          </div>
        )}
        <button
          aria-label={favoriteIds.has(product.id) ? 'Убрать из избранного' : 'Добавить в избранное'}
          aria-pressed={favoriteIds.has(product.id)}
          className={`product-card__favorite product-detail__favorite${favoriteIds.has(product.id) ? ' is-active' : ''}`}
          onClick={() => toggleFavorite(product.id)}
          type="button"
        >
          ♡
        </button>
      </section>
      <div className="product-detail__info">
        <p className="product-card__brand">{product.brand ?? product.category_name}</p>
        <h1>{product.title}</h1>
        {product.description && <p className="product-detail__description">{product.description}</p>}
        <section className="product-detail__sizes">
          <h2>РАЗМЕР:</h2>
          <div className="store-chip-row">
            {product.variants.map((variant) => (
              <SizeChip
                disabled={variant.stock <= 0}
                key={variant.id}
                onClick={() => setSelectedVariantId(variant.id)}
                selectionId={`product-size-${product.id}`}
                selected={selectedVariantId === variant.id}
                size={variant.size || 'ONE SIZE'}
              />
            ))}
          </div>
        </section>
        <div className="product-detail__price">
          <strong>{formatCurrency(product.price, currency)}</strong>
          {discounted && <del>{formatCurrency(product.original_price!, currency)}</del>}
        </div>
        {product.sold && <p className="store-inline-error">ТОВАР ПРОДАН</p>}
        {favoriteError != null && <p className="store-inline-error">{errorText(favoriteError)}</p>}
        {!selectedVariant && !product.sold && (
          <p className="product-detail__hint">Выберите доступный размер</p>
        )}
        <motion.button
          animate={{ scale: added && !reduceMotion ? [1, 1.025, 1] : 1 }}
          className="product-detail__add"
          disabled={!selectedVariant || selectedVariant.stock <= 0}
          onClick={addProduct}
          type="button"
          transition={{ duration: reduceMotion ? motionDuration.fade : 0.32 }}
        >
          <AnimatePresence initial={false} mode="wait">
            {added ? (
              <motion.span
                animate={{ opacity: 1, y: 0 }}
                aria-label="Добавлено в корзину"
                className="product-detail__added"
                exit={{ opacity: 0, y: 4 }}
                initial={{ opacity: 0, y: reduceMotion ? 0 : -4 }}
                key="added"
              >
                ДОБАВЛЕНО <span aria-hidden="true">✓</span>
              </motion.span>
            ) : (
              <motion.span
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: reduceMotion ? 0 : 4 }}
                initial={{ opacity: 0, y: reduceMotion ? 0 : -4 }}
                key="add"
              >
                ДОБАВИТЬ В КОРЗИНУ <span aria-hidden="true">↗</span>
              </motion.span>
            )}
          </AnimatePresence>
        </motion.button>
        <AnimatePresence>
          {toast && (
            <motion.p
              animate={{ opacity: 1, y: 0 }}
              className="store-toast"
              exit={{ opacity: 0 }}
              initial={{ opacity: 0, y: 8 }}
              role="status"
            >
              {toast}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
      <AnimatePresence>
        {flyingPhoto && (
          <motion.img
            alt=""
            aria-hidden="true"
            animate={{
              opacity: 0,
              scale: reduceMotion ? 1 : 0.16,
              x: reduceMotion ? 0 : flyingPhoto.toX - flyingPhoto.fromX,
              y: reduceMotion ? 0 : flyingPhoto.toY - flyingPhoto.fromY,
            }}
            className="product-fly-to-cart"
            initial={{ opacity: 0.95, scale: 1, x: 0, y: 0 }}
            onAnimationComplete={() => setFlyingPhoto(null)}
            src={flyingPhoto.src}
            style={{ left: flyingPhoto.fromX, top: flyingPhoto.fromY }}
            transition={{ duration: reduceMotion ? motionDuration.fade : 0.52, ease: motionEase.standard }}
          />
        )}
      </AnimatePresence>
    </article>
  )
}

function formatCurrency(value: number | string, currency: string): string {
  return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(value))} ${currency}`
}

export function CartScreen() {
  const location = useLocation()
  const reduceMotion = useReducedMotion()
  const [activeTab, setActiveTab] = useState<'cart' | 'favorites'>(() =>
    location.pathname === '/shop/favorites' ? 'favorites' : 'cart',
  )
  const { currency } = useCurrency()
  const {
    cart,
    cartCount,
    favoriteIds,
    setCartQuantity,
    removeFromCart,
    toggleFavorite,
    isCartLoading,
    isFavoritesLoading,
    cartError,
    favoriteError,
  } = useStoreState()
  const queryClient = useQueryClient()
  const { data: favorites, isLoading: favoritesLoading, isError: favoritesError, error, refetch } = useQuery({
    queryKey: ['store', 'favorites', currency],
    queryFn: ({ signal }) => getFavorites(currency, signal),
    enabled: activeTab === 'favorites' && isTMA(),
  })
  const cartData = cart

  if (!isTMA()) return <TelegramRequired />

  return (
    <section className="store-page">
      <h1 className="store-page__title">{activeTab === 'cart' ? 'МОЯ КОРЗИНА' : 'ИЗБРАННОЕ'}</h1>
      <div className="store-tab-switch">
        <button className={activeTab === 'cart' ? 'is-active' : ''} onClick={() => setActiveTab('cart')} type="button">
          МОЯ КОРЗИНА {cartCount > 0 && <span>{cartCount}</span>}
        </button>
        <button className={activeTab === 'favorites' ? 'is-active' : ''} onClick={() => setActiveTab('favorites')} type="button">
          ИЗБРАННОЕ {favoriteIds.size > 0 && <span>{favoriteIds.size}</span>}
        </button>
      </div>
      {activeTab === 'cart' && (
        <>
          {isCartLoading && <LoadingGrid />}
          {!isCartLoading && cartData?.items.length === 0 && (
            <EmptyState
              action={<Link className="ui-button ui-button--primary" to="/shop/clothing">ПЕРЕЙТИ В КАТАЛОГ</Link>}
              description="Добавьте товары из каталога, чтобы оформить заказ."
              title="КОРЗИНА ПОКА ПУСТА"
            />
          )}
          <AnimatePresence initial={false}>
          {cartData?.items.map((item) => (
            <motion.article
              className="cart-line"
              drag={reduceMotion ? false : 'x'}
              dragConstraints={{ left: -120, right: 0 }}
              dragElastic={0.08}
              key={item.variant_id}
              layout
              onDragEnd={(_, info) => {
                if (info.offset.x < -90) void removeFromCart(item.variant_id)
              }}
              transition={reduceMotion ? { duration: motionDuration.fade } : motionEase.spring}
              exit={{ opacity: 0, x: reduceMotion ? 0 : -72 }}
            >
              {item.image?.url ? <img alt="" src={item.image.thumbnail_url ?? item.image.url} /> : <div className="cart-line__placeholder" />}
              <div className="cart-line__body">
                <div className="cart-line__heading">
                  <div>
                    <h2>{item.title.toLocaleUpperCase('ru-RU')}</h2>
                    <p>РАЗМЕР: {item.size || 'УНИВЕРСАЛЬНЫЙ'}</p>
                  </div>
                  <button aria-label={`Удалить ${item.title}`} className="cart-line__remove" onClick={() => removeFromCart(item.variant_id)} type="button">×</button>
                </div>
                <div className="cart-line__bottom">
                  <QuantityStepper
                    max={Math.max(1, Math.min(item.stock, 99))}
                    onChange={(quantity) => setCartQuantity(item.variant_id, quantity)}
                    value={item.quantity}
                  />
                  <strong>{formatCurrency(item.line_total, currency)}</strong>
                </div>
              </div>
            </motion.article>
          ))}
          </AnimatePresence>
          {cartData && cartData.items.length > 0 && (
            <div className="cart-summary">
              <p><span>ТОВАРЫ ({cartCount})</span><AnimatedTotal currency={currency} value={cartData.items_total} /></p>
              <p><span>ДОСТАВКА</span><strong>УТОЧНЯЕТСЯ</strong></p>
              <p className="cart-summary__total"><span>ИТОГО</span><AnimatedTotal currency={currency} value={cartData.items_total} /></p>
              <Link className="ui-button ui-button--primary" to="/shop/checkout">ОФОРМИТЬ ЗАКАЗ</Link>
            </div>
          )}
          {cartError != null && <p className="store-inline-error">{errorText(cartError)}</p>}
          {cartError != null && (
            <button
              className="store-text-button"
              onClick={() => void queryClient.invalidateQueries({ queryKey: ['store', 'cart'] })}
              type="button"
            >
              ПОВТОРИТЬ ЗАГРУЗКУ
            </button>
          )}
        </>
      )}
      {activeTab === 'favorites' && (
        <>
          {(favoritesLoading || isFavoritesLoading) && <LoadingGrid />}
          {favoritesError && <ErrorState error={error} retry={() => refetch()} />}
          {favoriteError != null && <p className="store-inline-error">{errorText(favoriteError)}</p>}
          {!favoritesLoading && !favoritesError && favorites?.items.length === 0 && (
            <EmptyState
              action={<Link className="ui-button ui-button--primary" to="/shop/clothing">ПЕРЕЙТИ В КАТАЛОГ</Link>}
              description="Отмечайте сердцем товары, которые хотите сохранить."
              title="ИЗБРАННОЕ ПОКА ПУСТО"
            />
          )}
          {favorites && favorites.items.length > 0 && (
            <motion.div
              animate="visible"
              className="store-product-grid"
              initial="hidden"
              transition={{ staggerChildren: reduceMotion ? 0 : motionDuration.gridStagger }}
              variants={{ hidden: { opacity: 0 }, visible: { opacity: 1 } }}
            >
              {favorites.items.map((product) => (
                <ProductCard
                  isFavorite={favoriteIds.has(product.id)}
                  key={product.id}
                  onFavorite={toggleFavorite}
                  product={product}
                  sizeBadge={productSizeBadge(product)}
                />
              ))}
            </motion.div>
          )}
        </>
      )}
    </section>
  )
}

export function CheckoutScreen() {
  const { currency } = useCurrency()
  const { cart } = useStoreState()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const settingsQuery = useQuery({
    queryKey: storeKeys.settings(currency),
    queryFn: ({ signal }) => getPublicSettings(currency, signal),
    enabled: isTMA(),
  })
  const profileQuery = useQuery({
    queryKey: storeKeys.profile,
    queryFn: ({ signal }) => getCustomerProfile(signal),
    enabled: isTMA(),
  })
  const [methodId, setMethodId] = useState('')
  const [formError, setFormError] = useState('')
  const mutation = useMutation({
    mutationFn: createOrder,
    onSuccess: async (created: OrderCreated) => {
      await queryClient.invalidateQueries({ queryKey: ['store', 'cart'] })
      await queryClient.invalidateQueries({ queryKey: storeKeys.orders })
      let telegramOpenError: string | undefined
      if (openTelegramLink.isAvailable()) {
        try {
          openTelegramLink(created.manager_link)
        } catch {
          telegramOpenError = 'Не удалось открыть Telegram автоматически. Используйте кнопку ниже.'
        }
      } else {
        telegramOpenError = 'Откройте чат с менеджером кнопкой ниже.'
      }
      navigate('/shop/checkout/success', {
        state: { ...created, telegramOpenError },
      })
    },
    onError: (error) => setFormError(errorText(error)),
  })

  if (!isTMA()) return <TelegramRequired />
  if (settingsQuery.isLoading || profileQuery.isLoading) return <LoadingGrid />
  if (settingsQuery.isError) return <ErrorState error={settingsQuery.error} retry={() => settingsQuery.refetch()} />
  if (!cart?.items.length) {
    return (
      <EmptyState
        action={<Link className="ui-button ui-button--primary" to="/shop/clothing">ПЕРЕЙТИ В КАТАЛОГ</Link>}
        title="КОРЗИНА ПОКА ПУСТА"
      />
    )
  }
  const methods = settingsQuery.data?.delivery_methods ?? []
  const selectedMethod = methods.find((method) => method.id === methodId)

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const payload: CheckoutPayload = {
      recipient_name: String(form.get('recipient_name') ?? '').trim(),
      phone: String(form.get('phone') ?? '').trim(),
      delivery_method_id: methodId,
      city: String(form.get('city') ?? '').trim(),
      address: String(form.get('address') ?? '').trim() || undefined,
      branch: String(form.get('branch') ?? '').trim() || undefined,
      comment: String(form.get('comment') ?? '').trim() || undefined,
    }
    if (!payload.delivery_method_id) {
      setFormError('Выберите способ доставки.')
      return
    }
    if (selectedMethod?.code.toLowerCase() === 'courier' && !payload.address) {
      setFormError('Для курьера укажите полный адрес.')
      return
    }
    if (selectedMethod?.code.toLowerCase() !== 'courier' && !payload.address && !payload.branch) {
      setFormError('Укажите адрес или номер отделения доставки.')
      return
    }
    setFormError('')
    mutation.mutate(payload)
  }

  return (
    <section className="store-page">
      <p className="eyebrow">ПОКУПКА · {cart.item_count} ТОВАРА</p>
      <h1 className="store-page__title">ОФОРМЛЕНИЕ ЗАКАЗА</h1>
      <form className="checkout-form" onSubmit={submit}>
        <label className="form-field">
          <span>ИМЯ И ФАМИЛИЯ</span>
          <input autoComplete="name" defaultValue={profileQuery.data?.first_name ?? ''} maxLength={80} minLength={2} name="recipient_name" required />
        </label>
        <label className="form-field">
          <span>ТЕЛЕФОН</span>
          <input autoComplete="tel" maxLength={32} minLength={5} name="phone" required type="tel" />
        </label>
        <fieldset className="checkout-methods">
          <legend>СПОСОБ ДОСТАВКИ</legend>
          {settingsQuery.data?.delivery_methods.map((method) => (
            <DeliveryChoice
              currency={currency}
              key={method.id}
              method={method}
              onChange={setMethodId}
              selected={methodId === method.id}
            />
          ))}
          {methods.length === 0 && <p className="store-inline-error">Нет доступных способов доставки.</p>}
        </fieldset>
        <label className="form-field">
          <span>ГОРОД</span>
          <input autoComplete="address-level2" maxLength={60} minLength={2} name="city" required />
        </label>
        {selectedMethod?.code.toLowerCase() === 'courier' ? (
          <label className="form-field">
            <span>ПОЛНЫЙ АДРЕС</span>
            <input autoComplete="street-address" maxLength={150} minLength={3} name="address" required />
          </label>
        ) : (
          <div className="checkout-location">
            <label className="form-field">
              <span>АДРЕС (ЕСЛИ ЕСТЬ)</span>
              <input autoComplete="street-address" maxLength={150} name="address" />
            </label>
            <label className="form-field">
              <span>ОТДЕЛЕНИЕ</span>
              <input maxLength={100} name="branch" placeholder="Номер или адрес отделения" />
            </label>
          </div>
        )}
        <label className="form-field">
          <span>КОММЕНТАРИЙ</span>
          <textarea maxLength={200} name="comment" rows={3} />
        </label>
        <p className="checkout-note">Оплата наличными, детали подтвердит менеджер.</p>
        {formError && <p className="store-inline-error" role="alert">{formError}</p>}
        <button className="ui-button ui-button--primary checkout-submit" disabled={mutation.isPending || methods.length === 0} type="submit">
          {mutation.isPending ? 'ОФОРМЛЯЕМ…' : 'ОФОРМИТЬ ЗАКАЗ'}
        </button>
      </form>
    </section>
  )
}

function DeliveryChoice({
  method,
  selected,
  onChange,
  currency,
}: {
  method: DeliveryMethod
  selected: boolean
  onChange: (id: string) => void
  currency: StoreCurrency
}) {
  const cost =
    method.price == null
      ? method.price_note || 'по договорённости'
      : `${formatCurrency(method.price, currency)}`
  return (
    <label className={`checkout-method${selected ? ' is-selected' : ''}`}>
      <input checked={selected} name="delivery" onChange={() => onChange(method.id)} type="radio" />
      <span><strong>{deliveryLabel(method)}</strong><small>{cost}</small></span>
      <span className="checkout-method__check">{selected ? '✓' : ''}</span>
    </label>
  )
}

export function OrderSuccessScreen() {
  const location = useLocation()
  const navigate = useNavigate()
  const reduceMotion = useReducedMotion()
  const created = location.state as (OrderCreated & { telegramOpenError?: string }) | null
  const openChat = () => {
    const link = created?.manager_link
    if (!link) return
    if (openTelegramLink.isAvailable()) openTelegramLink(link)
    else window.open(link, '_blank', 'noopener,noreferrer')
  }
  return (
    <section className="checkout-success">
      <Suspense fallback={<div aria-hidden="true" className="checkout-success__mark">✓</div>}>
        <OrderSuccessAnimation />
      </Suspense>
      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className="checkout-success__content"
        initial={{ opacity: 0, y: reduceMotion ? 0 : 10 }}
        transition={{ delay: reduceMotion ? 0 : 0.18, duration: motionDuration.fade, ease: motionEase.standard }}
      >
        <p className="eyebrow">BRAND GRODNO</p>
        <h1>ЗАКАЗ ОФОРМЛЕН</h1>
        <p>
          {created?.order
            ? `Заказ №${created.order.id.slice(0, 8).toUpperCase()} создан. Менеджер подтвердит наличие, доставку и оплату.`
            : 'Заказ оформлен. Его статус можно посмотреть в разделе «Мои покупки».'}
        </p>
        {created?.telegramOpenError && <p className="store-inline-error" role="status">{created.telegramOpenError}</p>}
        <button className="ui-button ui-button--primary" disabled={!created?.manager_link} onClick={openChat} type="button">
          ОТКРЫТЬ ЧАТ С МЕНЕДЖЕРОМ
        </button>
        <Link className="underlined-link" to="/shop/orders">МОИ ПОКУПКИ</Link>
        <button className="store-text-button" onClick={() => navigate('/shop/clothing')} type="button">ПЕРЕЙТИ В КАТАЛОГ</button>
      </motion.div>
    </section>
  )
}

const statusNames: Record<string, string> = {
  pending: 'ОЖИДАЕТ ПОДТВЕРЖДЕНИЯ',
  processing: 'ПОДТВЕРЖДЁН',
  shipped: 'ОТПРАВЛЕН',
  completed: 'ДОСТАВЛЕН',
  cancelled: 'ОТМЕНЁН',
}

export function OrdersScreen() {
  const query = useQuery({
    queryKey: storeKeys.orders,
    queryFn: ({ signal }) => getOrders(signal),
    enabled: isTMA(),
  })
  const orderIds = query.data?.items.map((item) => item.id) ?? []
  const details = useQueries({
    queries: orderIds.map((id) => ({
      queryKey: storeKeys.order(id),
      queryFn: ({ signal }: { signal: AbortSignal }) => getOrder(id, signal),
      enabled: isTMA(),
    })),
  })
  if (!isTMA()) return <TelegramRequired />
  if (query.isLoading) return <LoadingGrid />
  if (query.isError) return <ErrorState error={query.error} retry={() => query.refetch()} />
  if (!query.data?.items.length) {
    return (
      <EmptyState
        action={<Link className="underlined-link" to="/shop/clothing">ПЕРЕЙТИ В КАТАЛОГ</Link>}
        description="После первого заказа здесь появится его статус и товар."
        title="ПОКУПОК ПОКА НЕТ"
      />
    )
  }
  return (
    <section className="store-page">
      <p className="eyebrow">ВАША ИСТОРИЯ</p>
      <h1 className="store-page__title">МОИ ПОКУПКИ</h1>
      {query.data.items.map((summary, index) => {
        const detail: OrderDetail | undefined = details[index]?.data
        const detailError = details[index]?.error
        return (
          <article className="order-card" key={summary.id}>
            <div className="order-card__top">
              <strong>ЗАКАЗ №{summary.id.slice(0, 8).toUpperCase()}</strong>
              <span className={`order-status order-status--${summary.status}`}>{statusNames[summary.status] ?? summary.status.toUpperCase()}</span>
            </div>
            <p className="order-card__date">{new Date(summary.created_at).toLocaleDateString('ru-RU')}</p>
            {details[index]?.isLoading && <div className="store-product-skeleton__line" />}
            {detailError && <p className="store-inline-error">{errorText(detailError)}</p>}
            {detail?.items.map((item, itemIndex) => (
              <p className="order-card__item" key={`${item.product_name}-${itemIndex}`}>
                {item.product_name} · {item.size} × {item.quantity}
              </p>
            ))}
            <div className="order-card__total">
              <span>{summary.delivery_method_name} · {summary.city}</span>
              <strong>{formatCurrency(summary.total, summary.currency)}</strong>
            </div>
          </article>
        )
      })}
    </section>
  )
}

export function ProfileScreen() {
  const { cartCount, favoriteIds } = useStoreState()
  const profileQuery = useQuery({
    queryKey: storeKeys.profile,
    queryFn: ({ signal }) => getCustomerProfile(signal),
    enabled: isTMA(),
  })
  const ordersQuery = useQuery({
    queryKey: storeKeys.orders,
    queryFn: ({ signal }) => getOrders(signal),
    enabled: isTMA(),
  })
  const profile = profileQuery.data
  if (!isTMA()) return <TelegramRequired />
  if (profileQuery.isLoading || ordersQuery.isLoading) return <LoadingGrid />
  if (profileQuery.isError) return <ErrorState error={profileQuery.error} retry={() => profileQuery.refetch()} />
  if (!profile) return <EmptyState title="ПРОФИЛЬ НЕДОСТУПЕН" />

  const name = [profile.first_name, profile.last_name]
    .filter(Boolean)
    .join(' ') || 'ПОКУПАТЕЛЬ'
  const avatar = profile.photo_url
  const count = ordersQuery.data?.total ?? 0
  return (
    <section className="store-page profile-page">
      <p className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</p>
      <div className="profile-identity">
        {avatar ? <img alt="" src={avatar} /> : <div className="profile-identity__avatar">{name.slice(0, 1)}</div>}
        <div>
          <h1>{name}</h1>
          <p>{profile.username ? `@${profile.username}` : `ID ${profile.telegram_id}`}</p>
          <span>{profile.is_admin ? 'АДМИНИСТРАТОР' : 'ПОКУПАТЕЛЬ'}</span>
        </div>
      </div>
      <div className="profile-stats">
        <div><strong>{count}</strong><span>ПОКУПОК</span></div>
        <div><strong>{favoriteIds.size}</strong><span>ИЗБРАННОЕ</span></div>
        <div><strong>{cartCount}</strong><span>В КОРЗИНЕ</span></div>
      </div>
      <nav className="profile-links">
        <Link to="/shop/orders"><span>МОИ ПОКУПКИ</span><small>{count}</small><b>›</b></Link>
        <Link to="/shop/delivery"><span>ДОСТАВКА</span><b>›</b></Link>
        <Link to="/shop/contact"><span>СВЯЗАТЬСЯ С МЕНЕДЖЕРОМ</span><b>›</b></Link>
        {profile.is_admin && <Link to="/admin"><span>ПАНЕЛЬ УПРАВЛЕНИЯ</span><b>›</b></Link>}
      </nav>
      {!ordersQuery.isError && count === 0 && (
        <EmptyState
          action={<Link className="underlined-link" to="/shop/clothing">ПЕРЕЙТИ В КАТАЛОГ</Link>}
          description="После первого заказа здесь появится его статус и товар."
          title="ПОКУПОК ПОКА НЕТ"
        />
      )}
      {ordersQuery.isError && <p className="store-inline-error">{errorText(ordersQuery.error)}</p>}
    </section>
  )
}

export function DeliveryScreen() {
  const { currency } = useCurrency()
  const query = useQuery({
    queryKey: storeKeys.settings(currency),
    queryFn: ({ signal }) => getPublicSettings(currency, signal),
  })
  if (query.isLoading) return <LoadingGrid />
  if (query.isError) return <ErrorState error={query.error} retry={() => query.refetch()} />
  return (
    <section className="store-page">
      <p className="eyebrow">BRAND GRODNO</p>
      <h1 className="store-page__title">ДОСТАВКА</h1>
      <div className="delivery-method-list">
        {query.data?.delivery_methods.map((method) => (
          <div className="delivery-method-row" key={method.id}>
              <strong>{deliveryLabel(method)}</strong>
            <span>{method.price == null ? method.price_note || 'по договорённости' : formatCurrency(method.price, currency)}</span>
          </div>
        ))}
      </div>
      <a className="underlined-link" href={query.data?.reviews_url} rel="noreferrer" target="_blank">ОТЗЫВЫ</a>
      <a className="ui-button ui-button--primary" href={`https://t.me/${query.data?.manager_username}`} rel="noreferrer" target="_blank">
        СВЯЗАТЬСЯ С МЕНЕДЖЕРОМ
      </a>
    </section>
  )
}

export function ContactScreen() {
  const { currency } = useCurrency()
  const query = useQuery({
    queryKey: storeKeys.settings(currency),
    queryFn: ({ signal }) => getPublicSettings(currency, signal),
  })
  if (query.isLoading) return <LoadingGrid />
  if (query.isError) return <ErrorState error={query.error} retry={() => query.refetch()} />
  const username = query.data?.manager_username
  return (
    <section className="store-page">
      <p className="eyebrow">BRAND GRODNO</p>
      <h1 className="store-page__title">МЕНЕДЖЕР</h1>
      <p className="product-detail__description">Если у вас есть вопросы по размеру, доставке или заказу — напишите нам.</p>
      {username && (
        <a className="ui-button ui-button--primary" href={`https://t.me/${username}`} rel="noreferrer" target="_blank">
          НАПИСАТЬ @{username.toUpperCase()}
        </a>
      )}
      {query.data?.reviews_url && <a className="underlined-link" href={query.data.reviews_url} rel="noreferrer" target="_blank">ОТЗЫВЫ ПОКУПАТЕЛЕЙ</a>}
    </section>
  )
}
