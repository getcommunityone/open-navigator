import { STATE_CODES } from '../lib/usStates'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'

/**
 * StateSelect — a single, canonical US-state dropdown shared by every filter
 * flyout (Places / Topics / Causes / Questions).
 *
 * Options come from the clean canonical {@link STATE_CODES} list (50 states +
 * DC, no dirty/duplicate entries) with full names looked up from
 * {@link STATE_CODE_TO_NAME}. The empty value is the "all states" sentinel.
 * `value` is always a 2-letter USPS code (or '' for all).
 */

// Build once: { code, name } sorted by full state name for a friendly dropdown.
const STATE_OPTIONS = STATE_CODES.map((code) => ({
  code,
  name: STATE_CODE_TO_NAME[code] ?? code,
})).sort((a, b) => a.name.localeCompare(b.name))

interface StateSelectProps {
  /** 2-letter USPS code, or '' for "all states". */
  value: string
  onChange: (code: string) => void
  /** Label for the empty option (e.g. "All States", "Any state"). */
  allLabel?: string
  className?: string
  id?: string
}

export default function StateSelect({
  value,
  onChange,
  allLabel = 'All States',
  className = '',
  id,
}: StateSelectProps) {
  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={
        className ||
        'w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary-500'
      }
    >
      <option value="">{allLabel}</option>
      {STATE_OPTIONS.map((s) => (
        <option key={s.code} value={s.code}>
          {s.name}
        </option>
      ))}
    </select>
  )
}
