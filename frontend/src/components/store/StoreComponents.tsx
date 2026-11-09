import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { Link, NavLink } from 'react-router'
import type { ReactNode } from 'react'
import { useStoreState } from '../../app/store-context'
import { triggerHaptic, triggerSelectionHaptic } from '../../telegram/haptics'
import type { ProductCardData } from '../../store/types'
import { motionDuration, motionEase } from '../../lib/motion'

const Lottie = lazy(async () => {
  const imported = await import('lottie-react')
  const interopDefault = imported.default as typeof imported.default & {
    default?: typeof imported.default
  }
  return { default: interopDefault.default ?? interopDefault }
})

type IconName = 'menu' | 'search' | 'cart' | 'clothing' | 'shoes' | 'heart' | 'profile' | 'close'

function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, ReactNode> = {
    menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
    search: <><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 4 4" /></>,
    cart: <><path d="M3 4h2l2.2 11.2a2 2 0 0 0 2 1.6h8.4a2 2 0 0 0 1.9-1.4L21 8H6" /><circle cx="9.5" cy="20" r="1" /><circle cx="17.5" cy="20" r="1" /></>,
    clothing: <><path d="m8 4 4 2 4-2 4 3-2 4-2-1v10H8V10l-2 1-2-4 4-3Z" /></>,
    shoes: <><path d="M4 15c2.5 0 4-1.4 5-4l1.5 1.5c1.2 1.2 3.2 2 5.3 2H19a2 2 0 0 1 2 2v2H4v-3.5Z" /><path d="M4 18.5h17" /></>,
    heart: <><path d="M20.8 8.8c0 5.2-8.8 11-8.8 11S3.2 14 3.2 8.8A4.7 4.7 0 0 1 12 6.4a4.7 4.7 0 0 1 8.8 2.4Z" /></>,
    profile: <><circle cx="12" cy="8" r="3.5" /><path d="M5 21a7 7 0 0 1 14 0" /></>,
    close: <><path d="m6 6 12 12M18 6 6 18" /></>,
  }

  return (
    <svg
      aria-hidden="true"
      fill="none"
      height="22"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.7"
      viewBox="0 0 24 24"
      width="22"
    >
      {paths[name]}
    </svg>
  )
}

export function Header({
  onMenu,
  onSearch,
}: {
  onMenu: () => void
  onSearch: () => void
}) {
  const { cartCount } = useStoreState()
  const reduceMotion = useReducedMotion()
  return (
    <header className="store-header">
      <button className="icon-button" aria-label="Открыть меню" onClick={onMenu}>
        <Icon name="menu" />
      </button>
      <Link aria-label="BRAND GRODNO — главная" className="store-header__logo" to="/">
        BRAND GRODNO
      </Link>
      <div className="store-header__actions">
        <button className="icon-button" aria-label="Поиск" onClick={onSearch}>
          <Icon name="search" />
        </button>
        <Link aria-label={`Корзина, товаров: ${cartCount}`} className="icon-button store-header__cart" data-cart-target="" to="/shop/cart">
          <Icon name="cart" />
          <AnimatePresence mode="wait">
            {cartCount > 0 && (
              <motion.span
                animate={{ opacity: 1, scale: reduceMotion ? 1 : [1, 1.32, 1] }}
                className="cart-badge"
                exit={{ opacity: 0, scale: reduceMotion ? 1 : 0.7 }}
                initial={{ opacity: 0, scale: reduceMotion ? 1 : 0.6 }}
                key={cartCount}
                transition={{ duration: reduceMotion ? motionDuration.fade : 0.28, ease: motionEase.standard }}
              >
                {cartCount > 99 ? '99+' : cartCount}
              </motion.span>
            )}
          </AnimatePresence>
        </Link>
      </div>
    </header>
  )
}

const navigation: Array<{ to: string; label: string; icon: IconName }> = [
  { to: '/shop/clothing', label: 'ОДЕЖДА', icon: 'clothing' },
  { to: '/shop/shoes', label: 'ОБУВЬ', icon: 'shoes' },
  { to: '/shop/favorites', label: 'ИЗБРАННОЕ', icon: 'heart' },
  { to: '/shop/cart', label: 'КОРЗИНА', icon: 'cart' },
  { to: '/shop/profile', label: 'ПРОФИЛЬ', icon: 'profile' },
]

export function BottomNav() {
  return (
    <nav className="store-bottom-nav" aria-label="Основная навигация">
      {navigation.map((item) => (
        <NavLink
          key={item.to}
          className={({ isActive }) => `store-bottom-nav__item${isActive ? ' is-active' : ''}`}
          onClick={triggerSelectionHaptic}
          to={item.to}
        >
          <Icon name={item.icon} />
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}

export function Drawer({
  open,
  onClose,
  side = 'left',
  title = 'BRAND GRODNO',
  children,
}: {
  open: boolean
  onClose: () => void
  side?: 'left' | 'right'
  title?: string
  children: ReactNode
}) {
  const reduceMotion = useReducedMotion()
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          animate={{ opacity: 1 }}
          className={`store-overlay store-overlay--${side}`}
          exit={{ opacity: 0 }}
          initial={{ opacity: 0 }}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) onClose()
          }}
        >
          <motion.aside
            animate={{ x: 0 }}
            aria-modal="true"
            className="store-drawer"
            exit={{ x: side === 'left' ? '-100%' : '100%' }}
            initial={{ x: side === 'left' ? '-100%' : '100%' }}
            drag={reduceMotion ? false : 'x'}
            dragConstraints={{
              left: side === 'left' ? -280 : 0,
              right: side === 'right' ? 280 : 0,
            }}
            dragElastic={0.08}
            onDragEnd={(_, info) => {
              if ((side === 'left' && info.offset.x < -90) ||
                  (side === 'right' && info.offset.x > 90)) onClose()
            }}
            role="dialog"
            transition={reduceMotion ? { duration: motionDuration.fade } : motionEase.sheetSpring}
          >
            <div className="store-drawer__top">
              <span className="store-logo-small">{title}</span>
              <button className="icon-button" aria-label="Закрыть меню" onClick={onClose}>
                <Icon name="close" />
              </button>
            </div>
            {children}
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export function BottomSheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}) {
  const reduceMotion = useReducedMotion()
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          animate={{ opacity: 1 }}
          className="store-overlay store-overlay--bottom"
          exit={{ opacity: 0 }}
          initial={{ opacity: 0 }}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) onClose()
          }}
        >
          <motion.section
            animate={{ y: 0 }}
            aria-modal="true"
            className="store-bottom-sheet"
            exit={{ y: '100%' }}
            initial={{ y: '100%' }}
            drag={reduceMotion ? false : 'y'}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={0.08}
            onDragEnd={(_, info) => {
              if (info.offset.y > 100) onClose()
            }}
            role="dialog"
            transition={reduceMotion ? { duration: motionDuration.fade } : motionEase.sheetSpring}
          >
            <div className="store-bottom-sheet__handle" />
            <div className="store-bottom-sheet__heading">
              <h2>{title}</h2>
              <button className="icon-button" aria-label="Закрыть" onClick={onClose}>
                <Icon name="close" />
              </button>
            </div>
            {children}
          </motion.section>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function formatPrice(price: number | string, currency: string): string {
  return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(price))} ${currency}`
}

export function ProductCard({
  product,
  onFavorite,
  isFavorite = false,
  sizeBadge,
  onAdd,
}: {
  product: ProductCardData
  onFavorite?: (productId: string) => void
  isFavorite?: boolean
  sizeBadge?: string
  onAdd?: (product: ProductCardData) => void
}) {
  const reduceMotion = useReducedMotion()
  const [particleBurst, setParticleBurst] = useState(false)
  const burstTimer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(burstTimer.current), [])
  const image = product.images[0]?.thumbnail_url ?? product.images[0]?.url
  const discount =
    product.original_price == null
      ? null
      : Math.round(
          (1 - Number(product.price) / Number(product.original_price)) * 100,
        )
  return (
    <motion.article
      className="product-card"
      variants={{
        hidden: { opacity: 0, y: reduceMotion ? 0 : 12 },
        visible: { opacity: 1, y: 0 },
      }}
      transition={reduceMotion ? { duration: motionDuration.fade } : motionEase.spring}
      whileTap={reduceMotion ? { opacity: 0.82 } : { scale: 0.985 }}
    >
      <Link className="product-card__image-link" to={`/shop/products/${product.id}`}>
        {image ? (
          <motion.img
            alt={product.title}
            className="product-card__image"
            layoutId={`product-photo-${product.id}-0`}
            loading="lazy"
            src={image}
          />
        ) : (
          <div className="product-card__image product-card__image--empty" aria-label="Нет фотографии" />
        )}
        {discount != null && discount > 0 && (
          <span className="product-card__flag">-{discount}%</span>
        )}
        {product.sold && (
          <span className="product-card__sold-overlay">ПРОДАНО</span>
        )}
        {sizeBadge && <span className="product-card__size">{sizeBadge}</span>}
      </Link>
      {product.images.length > 1 && (
        <div aria-label={`${product.images.length} фото`} className="product-card__gallery-progress">
          {product.images.map((image, index) => (
            <span className={index === 0 ? 'is-active' : ''} key={`${image.url}-${index}`} />
          ))}
        </div>
      )}
      {onFavorite && (
        <motion.button
          animate={isFavorite && particleBurst ? { scale: [1, 1.3, 1] } : { scale: 1 }}
          aria-label={isFavorite ? 'Убрать из избранного' : 'Добавить в избранное'}
          aria-pressed={isFavorite}
          className={`product-card__favorite${isFavorite ? ' is-active' : ''}`}
          onClick={() => {
            triggerHaptic()
            if (!isFavorite) {
              setParticleBurst(true)
              window.clearTimeout(burstTimer.current)
              burstTimer.current = window.setTimeout(() => setParticleBurst(false), 420)
            }
            onFavorite(product.id)
          }}
          transition={{ duration: reduceMotion ? motionDuration.fade : 0.32 }}
          whileTap={reduceMotion ? { opacity: 0.7 } : { scale: 0.88 }}
        >
          <Icon name="heart" />
          <AnimatePresence>
            {particleBurst && !reduceMotion && (
              <span aria-hidden="true" className="favorite-particles">
                {[
                  [-12, -14],
                  [0, -19],
                  [12, -14],
                  [-15, 1],
                  [15, 1],
                  [-8, 15],
                  [8, 15],
                ].map(([x, y], index) => (
                  <motion.span
                    animate={{ opacity: 0, scale: 0.25, x, y }}
                    className="favorite-particles__dot"
                    initial={{ opacity: 1, scale: 0.7 }}
                    key={index}
                    transition={{ duration: 0.38, ease: motionEase.standard }}
                  />
                ))}
              </span>
            )}
          </AnimatePresence>
        </motion.button>
      )}
      <div className="product-card__info">
        <Link className="product-card__title" to={`/shop/products/${product.id}`}>{product.title.toLocaleUpperCase('ru-RU')}</Link>
        <span className="product-card__brand">{product.brand ?? product.category_name}</span>
        <div className="product-card__prices">
          <strong>{formatPrice(product.price, product.currency)}</strong>
          {product.original_price != null && (
            <del>{formatPrice(product.original_price, product.currency)}</del>
          )}
        </div>
        {onAdd && (
          <button
            className="product-card__add"
            disabled={product.sold}
            onClick={() => onAdd(product)}
            type="button"
          >
            ДОБАВИТЬ В КОРЗИНУ
          </button>
        )}
      </div>
    </motion.article>
  )
}

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T
  options: Array<{ value: T; label: string }>
  onChange: (value: T) => void
  label: string
}) {
  return (
    <div aria-label={label} className="segmented-control" role="group">
      {options.map((option) => (
        <button
          aria-pressed={value === option.value}
          className={value === option.value ? 'is-selected' : ''}
          key={option.value}
          onClick={() => {
            triggerSelectionHaptic()
            onChange(option.value)
          }}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export function SizeChip({
  size,
  selected = false,
  disabled = false,
  onClick,
  selectionId,
}: {
  size: string
  selected?: boolean
  disabled?: boolean
  onClick?: () => void
  selectionId?: string
}) {
  const reduceMotion = useReducedMotion()
  return (
    <button
      aria-pressed={selected}
      className={`size-chip${selected ? ' is-selected' : ''}${selectionId ? ' size-chip--animated' : ''}`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {selected && selectionId && (
        <motion.span
          aria-hidden="true"
          className="size-chip__selection"
          layoutId={reduceMotion ? undefined : selectionId}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={reduceMotion ? { duration: motionDuration.fade } : motionEase.spring}
        />
      )}
      {size}
    </button>
  )
}

export function QuantityStepper({
  value,
  onChange,
  min = 1,
  max = 99,
}: {
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
}) {
  return (
    <div aria-label="Количество" className="quantity-stepper">
      <button aria-label="Уменьшить количество" disabled={value <= min} onClick={() => onChange(value - 1)} type="button">−</button>
      <output>{value}</output>
      <button aria-label="Увеличить количество" disabled={value >= max} onClick={() => onChange(value + 1)} type="button">+</button>
    </div>
  )
}

export function LottieAnimation({
  animationData,
  loop = true,
  className,
}: {
  animationData: object
  loop?: boolean
  className?: string
}) {
  const reduceMotion = useReducedMotion()
  return (
    <Suspense fallback={null}>
      <Lottie
        animationData={animationData}
        className={className}
        loop={reduceMotion ? false : loop}
        autoplay={!reduceMotion}
      />
    </Suspense>
  )
}
