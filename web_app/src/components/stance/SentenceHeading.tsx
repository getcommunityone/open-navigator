import type { ReactNode } from 'react'

/**
 * A heading written as a sentence with blanks that are the controls: "What did [Alabama] say about [data centers]?".
 * The props mirror the shared component another branch is building (`components/story/SentenceHeading`), so the two can be
 * merged into one afterwards: a template of text parts and blanks, each blank `{ id, label, value, display, options, onChange,
 * searchable? }`, and an optional "Try" row. Local addition: a blank may bring its own `control` (the place blank uses the
 * place popover, which also takes a community), shown instead of the select built from `options`.
 */
export interface BlankOption {
  value: string
  label: string
  group?: string
  hint?: string
}
export interface Blank {
  id: string
  /** The accessible name ("Place", "Topic"). */
  label: string
  value: string
  /** The text the blank shows for the current value. */
  display: string
  options: BlankOption[]
  onChange: (value: string) => void
  searchable?: boolean
  /** Replaces the select built from `options`. */
  control?: ReactNode
}
export type TemplatePart = string | { blank: string }
export interface Suggestion {
  label: string
  onPick: () => void
}
interface Props {
  template: TemplatePart[]
  blanks: Blank[]
  as?: 'h1' | 'h2'
  className?: string
  suggestions?: Suggestion[]
}

function BlankSelect({ b }: { b: Blank }) {
  const groups = [...new Set(b.options.map((o) => o.group ?? ''))]
  return (
    <span className="stance-blank-wrap">
      <select className="stance-blank" aria-label={b.label} value={b.value} onChange={(e) => b.onChange(e.target.value)}>
        {groups.map((g) => {
          const opts = b.options
            .filter((o) => (o.group ?? '') === g)
            .map((o) => (
              <option key={o.value} value={o.value} title={o.hint}>
                {o.label}
              </option>
            ))
          return g ? (
            <optgroup key={g} label={g}>
              {opts}
            </optgroup>
          ) : (
            opts
          )
        })}
      </select>
      <span aria-hidden="true" className="stance-blank-caret">
        ▾
      </span>
    </span>
  )
}

export default function SentenceHeading({ template, blanks, as: Tag = 'h1', className, suggestions }: Props) {
  return (
    <>
      <Tag className={`stance-sentence${className ? ` ${className}` : ''}`}>
        {template.map((part, i) => {
          if (typeof part === 'string') return <span key={i}>{part}</span>
          const b = blanks.find((x) => x.id === part.blank)
          if (!b) return null
          return <span key={i}>{b.control ?? <BlankSelect b={b} />}</span>
        })}
      </Tag>
      {suggestions && suggestions.length > 0 && (
        <p className="stance-try">
          Try:{' '}
          {suggestions.map((s) => (
            <button key={s.label} type="button" className="folio-link-btn" onClick={s.onPick}>
              {s.label}
            </button>
          ))}
        </p>
      )}
    </>
  )
}
