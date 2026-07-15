import type { CompanionTheme } from '../types/movie'

type CompanionWidgetProps = {
  open: boolean
  name: string
  message: string
  theme: CompanionTheme
}

export function CompanionWidget({ open, name, message, theme }: CompanionWidgetProps) {
  if (!open) return null

  return (
    <aside className={`companion-widget ${theme}`} aria-live="polite">
      <p className="eyebrow">{name}</p>
      <p>{message}</p>
    </aside>
  )
}
