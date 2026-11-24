import { useEffect, useId, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../../lib/api'
import { STATE_CODES } from '../../lib/usStates'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'

interface PlaceHit {
  city?: string | null
  state_code?: string | null
}

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

/** Community names for a state from the place lookup (GET /api/feed/places): real hits only, filtered to the chosen state. */
function useCityOptions(stateCode: string | undefined, text: string) {
  const [debounced, setDebounced] = useState(text)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(text.trim()), 300)
    return () => clearTimeout(t)
  }, [text])
  const stateName = stateCode ? STATE_CODE_TO_NAME[stateCode] : undefined
  const q = useQuery({
    queryKey: ['stance', 'places', stateCode ?? '', debounced.toLowerCase()],
    queryFn: async () => {
      const res = await api.get<{ results: PlaceHit[] }>('/feed/places', { params: { q: `${debounced}, ${stateName}` } })
      const seen = new Set<string>()
      const out: string[] = []
      for (const h of res.data?.results ?? []) {
        const c = (h.city ?? '').trim()
        if (!c || h.state_code !== stateCode || seen.has(c.toLowerCase())) continue
        seen.add(c.toLowerCase())
        out.push(c)
      }
      return out
    },
    enabled: Boolean(stateCode && stateName && debounced.length >= 3),
    staleTime: 10 * 60_000,
    retry: false,
  })
  return q.data ?? []
}

/** "Your place": a state select and a community input, in place. Changing either applies to the URL, label and results together. */
export default function PlaceControl({ stateCode, city, open, onOpenChange, onApply, variant = 'button', display }: Props) {
  const blank = variant === 'blank'
  const [draftCity, setDraftCity] = useState(city ?? '')
  const toggleRef = useRef<HTMLButtonElement>(null)
  const selectRef = useRef<HTMLSelectElement>(null)
  const listId = useId()
  const options = useCityOptions(stateCode, draftCity)

  useEffect(() => setDraftCity(city ?? ''), [city, stateCode])
  useEffect(() => {
    if (open) selectRef.current?.focus()
  }, [open])

  const apply = () => onApply(stateCode ?? null, draftCity.trim() || null)

  return (
    <div
      className={`stance-place${blank ? ' is-blank' : ''}`}
      onKeyDown={(e) => {
        if (e.key === 'Escape' && open) {
          e.stopPropagation()
          onOpenChange(false)
          toggleRef.current?.focus()
        }
      }}
    >
      <button
        type="button"
        ref={toggleRef}
        className={blank ? 'stance-blank' : 'folio-btn'}
        aria-expanded={open}
        aria-controls="stance-place-panel"
        aria-label={blank ? `Place, ${display ?? ''}` : undefined}
        onClick={() => onOpenChange(!open)}
      >
        {blank ? (
          <>
            {display} <span aria-hidden="true" className="stance-blank-caret">▾</span>
          </>
        ) : (
          <>Your place {open ? '↑' : '↓'}</>
        )}
      </button>
      {open && (
        <div className="stance-place-panel" id="stance-place-panel" role="group" aria-label="Your place">
          <label className="folio-field" htmlFor="stance-state">
            State
          </label>
          <select
            id="stance-state"
            ref={selectRef}
            className="folio-select"
            value={stateCode ?? ''}
            onChange={(e) => onApply(e.target.value || null, null)}
          >
            <option value="">{blank ? 'the United States' : 'National only'}</option>
            {STATE_CODES.map((c) => (
              <option key={c} value={c}>
                {STATE_CODE_TO_NAME[c] ?? c}
              </option>
            ))}
          </select>
          <label className="folio-field" htmlFor="stance-city">
            Community
          </label>
          <input
            id="stance-city"
            className="folio-select"
            type="text"
            list={listId}
            value={draftCity}
            maxLength={120}
            disabled={!stateCode}
            placeholder={stateCode ? 'Type a city or town' : 'Choose a state first'}
            onChange={(e) => setDraftCity(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                apply()
              }
            }}
          />
          <datalist id={listId}>
            {options.map((o) => (
              <option key={o} value={o} />
            ))}
          </datalist>
          <div className="stance-place-actions">
            <button type="button" className="folio-btn" disabled={!stateCode} onClick={apply}>
              Apply community
            </button>
            <button
              type="button"
              className="folio-btn"
              disabled={!stateCode && !city}
              onClick={() => {
                onApply(null, null)
                setDraftCity('')
              }}
            >
              Clear place
            </button>
          </div>
          <p className="stance-note">
            Suggestions come from a place lookup. Results match the community name you enter exactly, ignoring capital letters.
          </p>
        </div>
      )}
    </div>
  )
}
