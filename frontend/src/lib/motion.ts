export const motionDuration = {
  page: 0.25,
  panel: 0.32,
  entry: 0.42,
  entryReveal: 0.035,
  stagger: 0.12,
  gridStagger: 0.045,
  fade: 0.18,
} as const

export const motionEase = {
  standard: [0.22, 1, 0.36, 1] as const,
  spring: {
    type: 'spring' as const,
    stiffness: 420,
    damping: 38,
    mass: 0.8,
  },
  sheetSpring: {
    type: 'spring' as const,
    stiffness: 360,
    damping: 34,
    mass: 0.85,
  },
} as const
