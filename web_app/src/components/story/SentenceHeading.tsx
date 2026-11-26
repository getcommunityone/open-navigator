import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { filterOptions, groupOptions, moveActive, typeAhead, type PickerOption } from '../../utils/sentenceHeading'
import '../../styles/sentence-heading.css'

export type { PickerOption }

/** One blank in the sentence. */
export interface BlankPart {
  /** Stable id of the blank (for keys and tests), e.g. "metric". */
  id: string
  /** The blank's accessible name: "Metric", "Place". */
  label: string
  /** The current option's `value`. */
  value: string
  /** What the sentence shows for the current choice (usually the option label, lower-cased to read in a sentence). */
  display: string
  options: PickerOption[]
  onChange: (value: string) => void
  /** Show a type-to-filter field (default true when there are more than 7 options). */
  searchable?: boolean
}
export type SentencePart = string | BlankPart

export interface Suggestion {
  label: string
  onSelect: () => void
}

export interface SentenceHeadingProps {
  /** The sentence: plain text pieces and blanks, in order, e.g. ["What's the story with ", metricBlank, " in ", placeBlank, "?"]. */
  parts: SentencePart[]
  /** DOM id of the h2 (so a page can send focus to it). */
  headingId?: string
  /** One-click suggestions under the sentence. */
  suggestions?: Suggestion[]
  /** Label before the suggestions (default "Try"). */
  suggestionsLabel?: string
  /** A "Surprise me" button: `onSurprise` makes the change and returns a sentence to announce, or null when there is nothing else to pick. */
  surprise?: { label?: string; onSurprise: () => string | null }
  /** Anything that belongs right under the sentence: an orientation line, a small year control. */
  children?: ReactNode
}

function Blank({ part }: { part: BlankPart }) {
  const { label, value, display, options, onChange } = part
  const searchable = part.searchable ?? options.length > 7
  const uid = useId()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [alignRight, setAlignRight] = useState(false)
  const btn = useRef<HTMLButtonElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const list = useRef<HTMLDivElement>(null)
  const typed = useRef({ text: '', at: 0 })
  const flat = filterOptions(options, query)
  const groups = groupOptions(flat)
  const listId = `${uid}-list`
  const optId = (i: number) => `${uid}-opt-${i}`

  // Open on the current choice; keep the active row in view.
  const openPicker = () => {
    const r = btn.current?.getBoundingClientRect()
    setAlignRight(!!r && r.left + 480 > window.innerWidth)
    setQuery('')
    setActive(Math.max(0, options.findIndex((o) => o.value === value)))
    setOpen(true)
  }
  const close = (refocus = true) => {
    setOpen(false)
    if (refocus) btn.current?.focus()
  }
  const choose = (o: PickerOption | undefined) => {
    if (!o) return
    if (o.value !== value) onChange(o.value)
    close()
  }
  useEffect(() => {
    if (!open) return
    document.getElementById(optId(active))?.scrollIntoView({ block: 'nearest' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, active, query])
  useEffect(() => {
    if (open && !searchable) list.current?.focus()
  }, [open, searchable])

  const onKey = (e: KeyboardEvent) => {
    const k = e.key
    if (k === 'ArrowDown' || k === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => moveActive(a, k === 'ArrowDown' ? 1 : -1, flat.length))
    } else if ((k === 'Home' || k === 'End') && !searchable) {
      e.preventDefault()
      setActive(moveActive(active, k === 'Home' ? 'first' : 'last', flat.length))
    } else if (k === 'Enter') {
      e.preventDefault()
      choose(flat[active])
    } else if (k === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      close()
    } else if (k === 'Tab') {
      close(false)
    } else if (!searchable && k.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const now = Date.now()
      typed.current = { text: now - typed.current.at > 700 ? k : typed.current.text + k, at: now }
      const i = typeAhead(flat, typed.current.text, typed.current.text.length > 1 ? active : active + 1)
      if (i >= 0) setActive(i)
    }
  }

  if (options.length < 2) return <span className="sh-fixed">{display}</span>
  return (
    <span className="sh-blank">
      <button
        ref={btn}
        type="button"
        className="sh-blank-btn"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`${label}: ${display}. Change`}
        onClick={() => (open ? close() : openPicker())}
        onKeyDown={(e) => {
          if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
            e.preventDefault()
            openPicker()
          }
        }}
      >
        {display}
      </button>
      {open && (
        <>
          <div className="sh-backdrop" onClick={() => close(false)} aria-hidden="true" />
          <div className={`sh-pop${alignRight ? ' sh-pop-right' : ''}`} role="dialog" aria-label={label}>
            {searchable && (
              <input
                ref={input}
                autoFocus
                className="sh-search"
                type="text"
                role="combobox"
                aria-expanded="true"
                aria-controls={listId}
                aria-autocomplete="list"
                aria-activedescendant={flat.length ? optId(active) : undefined}
                aria-label={`Search ${label.toLowerCase()}`}
                placeholder={`Search ${label.toLowerCase()}…`}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setActive(0)
                }}
                onKeyDown={onKey}
              />
            )}
            <div
              ref={list}
              id={listId}
              className="sh-list"
              role="listbox"
              aria-label={label}
              tabIndex={searchable ? -1 : 0}
              aria-activedescendant={!searchable && flat.length ? optId(active) : undefined}
              onKeyDown={searchable ? undefined : onKey}
            >
              {flat.length === 0 && <p className="sh-empty">Nothing matches “{query}”.</p>}
              {groups.map((g, gi) => {
                const rows = g.items.map((o) => {
                  const i = flat.indexOf(o)
                  return (
                    <div
                      key={o.value}
                      id={optId(i)}
                      role="option"
                      aria-selected={o.value === value}
                      className={`sh-option${i === active ? ' is-active' : ''}${o.value === value ? ' is-current' : ''}`}
                      onMouseMove={() => i !== active && setActive(i)}
                      onClick={() => choose(o)}
                    >
                      <span className="sh-option-main">
                        <span className="sh-option-label">{o.label}</span>
                        {o.hint && <span className="sh-option-hint">{o.hint}</span>}
                      </span>
                      {o.value === value && (
                        <span className="sh-check" aria-hidden="true">
                          ✓
                        </span>
                      )}
                    </div>
                  )
                })
                return g.group ? (
                  <div key={g.group} role="group" aria-labelledby={`${uid}-g${gi}`}>
                    <p className="sh-group" id={`${uid}-g${gi}`}>
                      {g.group}
                    </p>
                    {rows}
                  </div>
                ) : (
                  <div key={`g${gi}`}>{rows}</div>
                )
              })}
            </div>
          </div>
        </>
      )}
    </span>
  )
}

/**
 * A page title that is a sentence the reader completes ("What's the story with [median household income] in [the United
 * States]?"). Each blank is a button that opens an inline picker (combobox with type-to-filter, grouped options with one-line
 * hints, the current choice marked; a bottom sheet on a phone) and sets whatever state the page keeps. Under the sentence:
 * optional children, a "Try" row of one-click suggestions and a "Surprise me" button. The sentence rises into view once, on
 * mount; changing a blank never replays it. Reusable for any "Verb [x] in [y]" page heading.
 */
export default function SentenceHeading({ parts, headingId, suggestions, suggestionsLabel = 'Try', surprise, children }: SentenceHeadingProps) {
  const [intro, setIntro] = useState(() => typeof window === 'undefined' || !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)
  const [said, setSaid] = useState('')
  useEffect(() => {
    const t = window.setTimeout(() => setIntro(false), 1300)
    return () => window.clearTimeout(t)
  }, [])
  return (
    <div className="sh">
      <h2 className="sh-title" id={headingId} tabIndex={-1}>
        <span className={`sh-mask${intro ? ' is-intro' : ''}`}>
          <span className="sh-inner">
            {parts.map((p, i) => (typeof p === 'string' ? <span key={i}>{p}</span> : <Blank key={p.id} part={p} />))}
          </span>
        </span>
      </h2>
      {children}
      {(suggestions?.length || surprise) && (
        <p className="sh-try">
          {!!suggestions?.length && <span className="sh-try-label">{suggestionsLabel}</span>}
          {suggestions?.map((s) => (
            <button key={s.label} type="button" className="sh-try-btn" onClick={s.onSelect}>
              {s.label}
            </button>
          ))}
          {surprise && (
            <button type="button" className="sh-try-btn sh-surprise" onClick={() => setSaid(surprise.onSurprise() ?? 'There is nothing else to show.')}>
              {surprise.label ?? 'Surprise me'}
            </button>
          )}
        </p>
      )}
      <p className="sh-sr" role="status" aria-live="polite">
        {said}
      </p>
    </div>
  )
}
