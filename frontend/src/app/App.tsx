import { lazy, Suspense, useEffect, useRef, useState, type FormEvent } from 'react'
import { AnimatePresence, MotionConfig, motion, useReducedMotion } from 'framer-motion'
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useSearchParams } from 'react-router'
import { useBackButton } from '../telegram/use-back-button'
import { motionDuration, motionEase } from '../lib/motion'
import {
  BottomNav,
  Drawer,
  EmptyState,
  Header,
  Skeleton,
} from '../components/ui'

const CartScreen = lazy(() =>
  import('../store/Screens').then((module) => ({ default: module.CartScreen })),
)
const CatalogScreen = lazy(() =>
  import('../store/Screens').then((module) => ({ default: module.CatalogScreen })),
)
const CheckoutScreen = lazy(() =>
  import('../store/Screens').then((module) => ({ default: module.CheckoutScreen })),
)
const ContactScreen = lazy(() =>
  import('../store/Screens').then((module) => ({ default: module.ContactScreen })),
)
const DeliveryScreen = lazy(() =>
  import('../store/Screens').then((module) => ({ default: module.DeliveryScreen })),
)
const EntryScreen = lazy(() =>
  import('../store/Screens').then((module) => ({ default: module.EntryScreen })),
)
const OrderSuccessScreen = lazy(() =>
  import('../store/Screens').then((module) => ({ default: module.OrderSuccessScreen })),
)
const OrdersScreen = lazy(() =>
  import('../store/Screens').then((module) => ({ default: module.OrdersScreen })),
)
const ProductScreen = lazy(() =>
  import('../store/Screens').then((module) => ({ default: module.ProductScreen })),
)
const ProfileScreen = lazy(() =>
  import('../store/Screens').then((module) => ({ default: module.ProfileScreen })),
)
const AdminPanel = lazy(() =>
  import('../store/AdminPanel').then((module) => ({ default: module.AdminPanel })),
)

const AddBusinessScreen = lazy(() =>
  import('../features/catalog/screens/AddBusinessScreen').then((module) => ({
    default: module.AddBusinessScreen,
  })),
)
const FavoritesScreen = lazy(() =>
  import('../features/catalog/screens/FavoritesScreen').then((module) => ({
    default: module.FavoritesScreen,
  })),
)
const HomeScreen = lazy(() =>
  import('../features/catalog/screens/HomeScreen').then((module) => ({
    default: module.HomeScreen,
  })),
)
const PlaceScreen = lazy(() =>
  import('../features/catalog/screens/PlaceScreen').then((module) => ({
    default: module.PlaceScreen,
  })),
)
const PlacesScreen = lazy(() =>
  import('../features/catalog/screens/PlacesScreen').then((module) => ({
    default: module.PlacesScreen,
  })),
)
const ReviewsScreen = lazy(() =>
  import('../features/catalog/screens/ReviewsScreen').then((module) => ({
    default: module.ReviewsScreen,
  })),
)

function PlaceholderPage({ title }: { title: string }) {
  return <EmptyState title={title} description="Раздел будет доступен в следующем этапе." />
}

function PageLoading() {
  return (
    <div aria-busy="true" className="screen-stack">
      <Skeleton height={12} width="35%" />
      <Skeleton height={54} width="82%" />
      <Skeleton height={180} />
    </div>
  )
}

function EntryRoute() {
  return window.localStorage.getItem('store-entry-selected') === 'true'
    ? <Navigate replace to="/shop/clothing" />
    : <EntryScreen />
}

function routeOrder(path: string): number {
  if (path === '/' || path === '/welcome') return 0
  if (path.includes('/products/')) return 2
  if (path.includes('/checkout')) return 4
  if (path.endsWith('/cart') || path.endsWith('/favorites')) return 3
  if (path.endsWith('/orders') || path.endsWith('/profile')) return 5
  if (path.includes('/shop/')) return 1
  return 3
}

export function App() {
  useBackButton()
  const location = useLocation()
  const navigate = useNavigate()
  const adminOpen = location.pathname === '/admin'
  const [searchParams] = useSearchParams()
  const reduceMotion = useReducedMotion()
  const previousPath = useRef(location.pathname)
  const pageDirection = routeOrder(location.pathname) >= routeOrder(previousPath.current) ? 1 : -1
  const [menuOpen, setMenuOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchText, setSearchText] = useState(searchParams.get('q') ?? '')
  const entryOpen =
    location.pathname === '/welcome' ||
    (location.pathname === '/' &&
      window.localStorage.getItem('store-entry-selected') !== 'true')
  useEffect(() => {
    previousPath.current = location.pathname
    window.scrollTo({ top: 0, behavior: 'auto' })
  }, [location.pathname])

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false)
        setSearchOpen(false)
      }
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [])

  useEffect(() => {
    setSearchText(searchParams.get('q') ?? '')
  }, [searchParams])

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const params = new URLSearchParams()
    if (searchText.trim()) params.set('q', searchText.trim())
    navigate(`/shop/${location.pathname.includes('/shoes') ? 'shoes' : 'clothing'}${params.size ? `?${params}` : ''}`)
    setSearchOpen(false)
  }

  return (
    <MotionConfig reducedMotion="user">
    <div className="app-shell">
      {!entryOpen && !adminOpen && <Header onMenu={() => setMenuOpen(true)} onSearch={() => setSearchOpen(true)} />}

      <AnimatePresence custom={pageDirection} mode="wait" initial={false}>
        <motion.main
          animate="center"
          className="app-main"
          custom={pageDirection}
          exit="exit"
          initial="enter"
          key={location.pathname}
          transition={{ duration: reduceMotion ? motionDuration.fade : motionDuration.page, ease: motionEase.standard }}
          variants={{
            enter: (direction: number) => ({ opacity: 0, x: reduceMotion ? 0 : direction * 20 }),
            center: { opacity: 1, x: 0 },
            exit: (direction: number) => ({ opacity: 0, x: reduceMotion ? 0 : direction * -20 }),
          }}
        >
          <Suspense fallback={<PageLoading />}>
            <Routes location={location}>
              <Route path="/" element={<EntryRoute />} />
              <Route path="/welcome" element={<EntryScreen />} />
              <Route path="/shop/clothing" element={<CatalogScreen group="clothing" />} />
              <Route path="/shop/shoes" element={<CatalogScreen group="shoes" />} />
              <Route path="/shop/favorites" element={<CartScreen />} />
              <Route path="/shop/cart" element={<CartScreen />} />
              <Route path="/shop/profile" element={<ProfileScreen />} />
              <Route path="/shop/products/:productId" element={<ProductScreen />} />
              <Route path="/shop/checkout" element={<CheckoutScreen />} />
              <Route path="/shop/checkout/success" element={<OrderSuccessScreen />} />
              <Route path="/shop/orders" element={<OrdersScreen />} />
              <Route path="/shop/delivery" element={<DeliveryScreen />} />
              <Route path="/shop/contact" element={<ContactScreen />} />
              <Route path="/admin" element={<AdminPanel />} />
              <Route path="/local-catalog" element={<HomeScreen />} />
              <Route path="/places" element={<PlacesScreen />} />
              <Route path="/places/:placeId" element={<PlaceScreen />} />
              <Route path="/places/:placeId/reviews" element={<ReviewsScreen />} />
              <Route path="/favorites" element={<FavoritesScreen />} />
              <Route path="/add-business" element={<AddBusinessScreen />} />
              <Route path="*" element={<PlaceholderPage title="СТРАНИЦА НЕ НАЙДЕНА" />} />
            </Routes>
          </Suspense>
        </motion.main>
      </AnimatePresence>

      {!entryOpen && !adminOpen && <BottomNav />}

      <Drawer open={menuOpen} onClose={() => setMenuOpen(false)}>
        <div className="store-drawer__content">
          <Link className="store-drawer__link" onClick={() => setMenuOpen(false)} to="/shop/favorites">ИЗБРАННОЕ <b>›</b></Link>
          <Link className="store-drawer__link" onClick={() => setMenuOpen(false)} to="/shop/profile">ПРОФИЛЬ <b>›</b></Link>
          <Link className="store-drawer__link" onClick={() => setMenuOpen(false)} to="/shop/orders">МОИ ПОКУПКИ <b>›</b></Link>
          <Link className="store-drawer__link" onClick={() => setMenuOpen(false)} to="/shop/delivery">ДОСТАВКА <b>›</b></Link>
          <Link className="store-drawer__link" onClick={() => setMenuOpen(false)} to="/shop/contact">СВЯЗАТЬСЯ С МЕНЕДЖЕРОМ <b>›</b></Link>
        </div>
      </Drawer>

      <Drawer open={searchOpen} onClose={() => setSearchOpen(false)} side="right" title="ПОИСК">
        <form className="store-drawer__content" onSubmit={submitSearch}>
          <label className="eyebrow" htmlFor="store-search">НАЗВАНИЕ ИЛИ БРЕНД</label>
          <input autoFocus className="store-search-input" id="store-search" onChange={(event) => setSearchText(event.target.value)} placeholder="Что ищем?" type="search" value={searchText} />
          <button className="ui-button ui-button--primary" type="submit">НАЙТИ</button>
        </form>
      </Drawer>
    </div>
    </MotionConfig>
  )
}
