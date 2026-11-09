import { useEffect, useState } from 'react'
import { useReducedMotion } from 'framer-motion'
import { LottieAnimation } from '../components/store/StoreComponents'

export function OrderSuccessAnimation() {
  const reduceMotion = useReducedMotion()
  const [animationData, setAnimationData] = useState<object | null>(null)

  useEffect(() => {
    if (reduceMotion) return
    const controller = new AbortController()
    void fetch('/animations/order-success.json', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Animation request failed: ${response.status}`)
        return response.json() as Promise<object>
      })
      .then(setAnimationData)
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          console.error('Не удалось загрузить анимацию подтверждения заказа.', error)
        }
      })
    return () => controller.abort()
  }, [reduceMotion])

  if (!animationData || reduceMotion) {
    return <div aria-hidden="true" className="checkout-success__mark">✓</div>
  }
  return (
    <LottieAnimation
      animationData={animationData}
      className="checkout-success__animation"
      loop={false}
    />
  )
}
