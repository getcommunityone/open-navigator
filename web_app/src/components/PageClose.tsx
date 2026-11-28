import { useCallback, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { closeDestination, previousEntry } from '../lib/pageClose'

/**
 * The one exit of every full-screen sub-page (#1405), the same look as the story's Close (#1342): a 44px x with a small
 * "Close" caption at the top right of the content header, below the site header so it never touches the place toggle.
 * Goes back when the previous entry is ours, else home with the scope kept (see `lib/pageClose.ts`). Escape closes too,
 * unless a dialog or a field has focus.
 */
export function usePageClose(): { close: () => void; label: string } {
  const navigate = useNavigate()
  const { pathname, search } = useLocation()
  const label = closeDestination({ pathname, search }, previousEntry()).label
  const close = useCallback(() => {
    const d = closeDestination({ pathname, search }, previousEntry())
    if (d.kind === 'back') navigate(-1)
    else navigate(d.to)
  }, [navigate, pathname, search])
  return { close, label }
}

/** The × with its "Close" caption; shared by the page row and the Settings dialog. */
export function CloseButton({ onClick, label, aria = 'Close page' }: { onClick: () => void; label: string; aria?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={aria}
      title={`Close · back to ${label}`}
      data-testid="page-close"
      className="inline-flex h-11 w-11 flex-col items-center justify-center rounded-full border-0 bg-transparent p-0 text-stone-900 hover:bg-stone-900/10 focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-2 focus-visible:outline-teal-700"
    >
      <span aria-hidden="true" className="text-[28px] leading-none">×</span>
      <span aria-hidden="true" className="-mt-1 text-[10px] font-bold leading-none tracking-wide">Close</span>
    </button>
  )
}

export default function PageClose() {
  const { close, label } = usePageClose()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      if (document.querySelector('[role="dialog"][aria-modal="true"], dialog[open], [data-sheet-open]')) return
      const ae = document.activeElement as HTMLElement | null
      if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'SELECT' || ae.tagName === 'TEXTAREA' || ae.isContentEditable)) return
      if (ae?.closest?.('[data-map-keys][data-map-active], [data-keeps-escape]')) return
      close()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [close])

  return (
    <div className="flex h-11 w-full justify-end pr-2" data-testid="page-close-row">
      <CloseButton onClick={close} label={label} />
    </div>
  )
}
