import {
  hapticFeedbackImpactOccurred,
  isTMA,
  hapticFeedbackSelectionChanged,
} from '@telegram-apps/sdk'

export function triggerHaptic(): void {
  if (isTMA() && hapticFeedbackImpactOccurred.isAvailable()) {
    hapticFeedbackImpactOccurred('light')
  }
}

export function triggerSelectionHaptic(): void {
  if (isTMA() && hapticFeedbackSelectionChanged.isAvailable()) {
    hapticFeedbackSelectionChanged()
  }
}
