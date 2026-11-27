import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

interface Props {
  /** Where Close goes: `storyCloseHref(storyId, scopeQuery)`, the home page with the scope kept. */
  to: string
  /** False while a dialog is open, so Escape closes the dialog, not the story. */
  escape?: boolean
}

/**
 * The story's one exit (#1234, owner 2026-11-27: "consistent Close in top right"): a 44px × in the top-right corner of every
 * story (the Data Center Story and the topic stories), at the same place and size everywhere, named "Close story". It goes
 * back to the home page with the place kept, where the reader picks the next story. Escape closes too. Shared by
 * `ScopeBar` and the topic stories.
 */
export default function StoryClose({ to, escape = true }: Props) {
  const navigate = useNavigate()
  useEffect(() => {
    if (!escape) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      // An open dialog or a field keeps its own Escape.
      const ae = document.activeElement as HTMLElement | null
      if (document.querySelector('[role="dialog"][aria-modal="true"], dialog[open]')) return
      if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'SELECT' || ae.tagName === 'TEXTAREA')) return
      // A story map showing a state's card: its Escape hides the card (#1277), not the story.
      if (ae?.closest?.('[data-map-keys][data-map-active]')) return
      // A KPI list that is open and focused (#1288): its Escape closes the list, not the story.
      if (ae?.closest?.('[data-keeps-escape]')) return
      navigate(to)
    }
    // Capture phase: this runs before a dialog's own Escape closes it, so an open dialog is still seen and keeps its Escape.
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [to, escape, navigate])
  return (
    <button type="button" className="story-close" aria-label="Close story" title="Close story" data-testid="story-close" onClick={() => navigate(to)}>
      <span aria-hidden="true">×</span>
    </button>
  )
}
