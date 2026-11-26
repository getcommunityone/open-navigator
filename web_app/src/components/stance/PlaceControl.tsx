import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { LocationData } from '../../contexts/LocationContext'
import { STATE_CODES } from '../../lib/usStates'
import { countyNotice, placeToScope } from '../../utils/placeScope'
import { resolveCoordsToLocation, resolveQueryToChoices, resolveZipToChoices } from '../../utils/resolvePlace'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'

interface Props {
  stateCode: string | undefined
  city: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onApply: (stateCode: string | null, city: string | null) => void
  /** `blank`: the toggle is an inline, underlined blank in a sentence ("What did [Alabama] say ...") and "National only" reads "the United States". */
  variant?: 'button' | 'blank'
  /** The blank's current text (the place label). */
  display?: string
}

interface Suggestion {
  key: string
  text: string
  loc: LocationData
}

const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), select:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'

/** A readable name for a resolved place: "Tuscaloosa, Alabama" or "Jefferson County, Alabama". */
function suggestionText(loc: LocationData): string {
  const state = STATE_CODE_TO_NAME[loc.state] ?? loc.state
  const place = loc.city || (loc.county ? (/county$/i.test(loc.county) ? loc.county : `${loc.county} County`) : '')
  return [place, state].filter(Boolean).join(', ')
}

/**
 * "Your place": a dialog with one search box (city, county or ZIP), one-click "the United States" / "All of [state]",
 * and a state list. It reads the same geocoder helpers as the home page's location search (utils/resolvePlace) but
 * never touches the saved site-wide location; the page's `?state=&city=` stays the authority via `onApply`.
 */
export default function PlaceControl({ stateCode, city, open, onOpenChange, onApply, variant = 'button', display }: Props) {
  const blank = variant === 'blank'
  const toggleRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const wasOpen = useRef(false)
  const requestId = useRef(0)
  const uid = useId()
  const titleId = `${uid}-title`
  const listId = `${uid}-list`

  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [active, setActive] = useState(-1)
  const [status, setStatus] = useState<'idle' | 'loading' | 'empty' | 'error'>('idle')
  const [notice, setNotice] = useState<string | null>(null)
  const [locating, setLocating] = useState(false)

  const stateName = stateCode ? STATE_CODE_TO_NAME[stateCode] : undefined
  const close = useCallback(() => onOpenChange(false), [onOpenChange])

  // Focus goes into the dialog on open and back to the blank on close.
  useEffect(() => {
    if (open) {
      wasOpen.current = true
      setQuery('')
      setSuggestions([])
      setActive(-1)
      setStatus('idle')
      setNotice(null)
      inputRef.current?.focus()
    } else if (wasOpen.current) {
      wasOpen.current = false
      toggleRef.current?.focus()
    }
  }, [open])

  // Look up as the person types; a ZIP and a name go through the same helpers the home page uses.
  useEffect(() => {
    const q = query.trim()
    const isZip = /^\d{5}$/.test(q)
    if (!open || (q.length < 3 && !isZip)) {
      requestId.current += 1
      setSuggestions([])
      setStatus('idle')
      return
    }
    const id = ++requestId.current
    setStatus('loading')
    const t = setTimeout(async () => {
      try {
        const choices = isZip ? await resolveZipToChoices(q) : await resolveQueryToChoices(q)
        if (id !== requestId.current) return
        const seen = new Set<string>()
        const out: Suggestion[] = []
        for (const c of choices) {
          if (!placeToScope(c.loc)) continue
          const text = suggestionText(c.loc)
          if (seen.has(text)) continue
          seen.add(text)
          out.push({ key: text, text, loc: c.loc })
        }
        setSuggestions(out)
        setActive(out.length ? 0 : -1)
        setStatus(out.length ? 'idle' : 'empty')
      } catch {
        if (id !== requestId.current) return
        setSuggestions([])
        setStatus('error')
      }
    }, 300)
    return () => clearTimeout(t)
  }, [query, open])

  const pick = (loc: LocationData) => {
    const scope = placeToScope(loc)
    if (!scope) return
    onApply(scope.stateCode, scope.city)
    const note = countyNotice(scope)
    if (note) {
      // A county has no city grain here: the state is applied, and the dialog says so.
      setNotice(note)
      setSuggestions([])
      setStatus('idle')
      setQuery('')
    } else {
      close()
    }
  }

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setStatus('error')
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const loc = await resolveCoordsToLocation(pos.coords.latitude, pos.coords.longitude)
          if (loc && placeToScope(loc)) pick(loc)
          else setStatus('empty')
        } catch {
          setStatus('error')
        } finally {
          setLocating(false)
        }
      },
      () => {
        setLocating(false)
        setStatus('error')
      },
      { timeout: 10000 },
    )
  }

  const onDialogKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation()
      close()
      return
    }
    if (e.key === 'Tab' && dialogRef.current) {
      const items = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE))
      if (!items.length) return
      const first = items[0]
      const last = items[items.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
  }

  const onInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown' && suggestions.length) {
      e.preventDefault()
      setActive((i) => (i + 1) % suggestions.length)
    } else if (e.key === 'ArrowUp' && suggestions.length) {
      e.preventDefault()
      setActive((i) => (i <= 0 ? suggestions.length - 1 : i - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const s = suggestions[active >= 0 ? active : 0]
      if (s) pick(s.loc)
    }
  }

  const choose = (code: string | null) => {
    onApply(code, null)
    close()
  }

  // The dialog sits inside the page's `.folio` root so it keeps the house tokens, but outside the heading it was opened from.
  const host = typeof document === 'undefined' ? null : (toggleRef.current?.closest('.folio') as HTMLElement | null) ?? document.body

  const dialog = open && host && (
    <div
      className="stance-dialog-scrim"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close()
      }}
    >
      <div
        ref={dialogRef}
        className="stance-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={onDialogKeyDown}
      >
        <div className="stance-dialog-head">
          <h2 id={titleId} className="stance-dialog-title">
            Choose a place
          </h2>
          <button type="button" className="stance-dialog-close" aria-label="Close" onClick={close}>
            <span aria-hidden="true">×</span>
          </button>
        </div>

        <label className="folio-field" htmlFor={`${uid}-q`}>
          City, county or ZIP
        </label>
        <input
          id={`${uid}-q`}
          ref={inputRef}
          className="folio-select stance-dialog-input"
          type="text"
          role="combobox"
          aria-expanded={suggestions.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 && suggestions[active] ? `${uid}-opt-${active}` : undefined}
          autoComplete="off"
          maxLength={120}
          value={query}
          placeholder="Tuscaloosa, Jefferson County or 35401"
          onChange={(e) => {
            setQuery(e.target.value)
            setNotice(null)
          }}
          onKeyDown={onInputKeyDown}
        />
        <ul id={listId} className="stance-dialog-list" role="listbox" aria-label="Matching places" hidden={suggestions.length === 0}>
          {suggestions.map((s, i) => (
            <li
              key={s.key}
              id={`${uid}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              className={`stance-dialog-option${i === active ? ' is-active' : ''}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => pick(s.loc)}
              onMouseEnter={() => setActive(i)}
            >
              {s.text}
            </li>
          ))}
        </ul>
        <p className="stance-note" role="status" aria-live="polite">
          {status === 'loading' && 'Looking up places...'}
          {status === 'empty' && 'No place found for that. Try a city, county or ZIP in the United States.'}
          {status === 'error' && "We couldn't look up places right now. You can still pick a state below."}
          {status === 'idle' && notice}
        </p>

        <div className="stance-dialog-quick">
          <button type="button" className="folio-btn" onClick={() => choose(null)}>
            {blank ? 'The United States' : 'National only'}
          </button>
          {stateCode && (
            <button type="button" className="folio-btn" onClick={() => choose(stateCode)}>
              All of {stateName ?? stateCode}
            </button>
          )}
          {typeof navigator !== 'undefined' && 'geolocation' in navigator && (
            <button type="button" className="folio-btn" disabled={locating} onClick={useMyLocation}>
              {locating ? 'Locating...' : 'Use my location'}
            </button>
          )}
        </div>

        <label className="folio-field" htmlFor={`${uid}-state`}>
          Or pick a state
        </label>
        <select
          id={`${uid}-state`}
          className="folio-select stance-dialog-input"
          value={stateCode && !city ? stateCode : ''}
          onChange={(e) => e.target.value && choose(e.target.value)}
        >
          <option value="">{stateCode && city ? `${stateName ?? stateCode} (city chosen)` : 'Choose a state'}</option>
          {STATE_CODES.map((c) => (
            <option key={c} value={c}>
              {STATE_CODE_TO_NAME[c] ?? c}
            </option>
          ))}
        </select>
      </div>
    </div>
  )

  return (
    <div className={`stance-place${blank ? ' is-blank' : ''}`}>
      <button
        type="button"
        ref={toggleRef}
        className={blank ? 'stance-blank' : 'folio-btn'}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={blank ? `Place, ${display ?? ''}` : undefined}
        onClick={() => onOpenChange(!open)}
      >
        {blank ? (
          <>
            {display} <span aria-hidden="true" className="stance-blank-caret">▾</span>
          </>
        ) : (
          <>Your place</>
        )}
      </button>
      {dialog && createPortal(dialog, host)}
    </div>
  )
}
