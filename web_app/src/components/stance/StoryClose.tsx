import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'

interface Props {
  /** Where Close goes: home, keeping the scope (`/?state=CA`). */
  to: string
  /** False while a dialog owns Escape (the place picker). */
  escape?: boolean
}

/**
 * Close (×) at the top right of a story (#1224, owner 2026-11-27): the same box on every screen, the story's one exit. It
 * returns home with the scope kept, and Escape does the same unless a dialog or field has the key.
 */
export default function StoryClose({ to, escape = true }: Props) {
  const navigate = useNavigate()
  useEffect(() => {
    if (!escape) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      const t = e.target as HTMLElement | null
      if (t?.closest?.('input, select, textarea, [role="dialog"], [role="listbox"]') || document.querySelector('[role="dialog"]')) return
      navigate(to)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [escape, navigate, to])
  return (
    <Link to={to} className="story-close" aria-label="Close story" title="Close story (Esc)" data-testid="story-close">
      <span aria-hidden="true">×</span>
    </Link>
  )
}
