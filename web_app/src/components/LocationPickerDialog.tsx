import { useEffect, useId, useRef } from 'react'
import AddressLookup from './AddressLookup'
import type { LocationData } from '../contexts/LocationContext'

const TEAL_DARK = '#0f766e'

interface Props {
  open: boolean
  onClose: () => void
  /** The place set now ("Tuscaloosa, AL"), or null when none is. */
  current: string | null
  onPicked: (loc: LocationData) => void
}

/**
 * The "Find your town" picker (#1179, shared since #1191): a centred dialog over the real geocoder
 * (AddressLookup → api/routes/geocode.py → Nominatim). Opened from the header's place control and the home page.
 * No place is suggested or hard-coded: any town the geocoder finds can be picked.
 */
export default function LocationPickerDialog({ open, onClose, current, onPicked }: Props) {
  const titleId = useId()
  const panelRef = useRef<HTMLDivElement>(null)

  // Escape closes; focus moves into the dialog on open and back to whatever opened it on close.
  useEffect(() => {
    if (!open) return
    const opener = document.activeElement as HTMLElement | null
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }
    document.addEventListener('keydown', onKey, true)
    const raf = requestAnimationFrame(() => {
      const first = panelRef.current?.querySelector<HTMLElement>('input, button, [href], [tabindex]:not([tabindex="-1"])')
      first?.focus()
    })
    return () => {
      document.removeEventListener('keydown', onKey, true)
      cancelAnimationFrame(raf)
      if (opener && document.contains(opener)) opener.focus()
    }
  }, [open, onClose])

  if (!open) return null
  return (
    <div
      className="fixed inset-0 bg-black/50 z-[70] flex items-center justify-center p-4"
      onClick={onClose}
      style={{ animation: 'fadeIn 150ms ease' }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="bg-white rounded-2xl shadow-2xl p-6 sm:p-8 max-w-2xl w-full text-left"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 id={titleId} className="text-2xl font-bold" style={{ color: TEAL_DARK, fontFamily: 'Playfair Display, Georgia, serif' }}>
            {current ? 'Change your location' : 'Find your community'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="hover:bg-stone-100"
            style={{ padding: 8, borderRadius: 10, border: 'none', background: 'none', color: '#78716c', fontSize: 20, cursor: 'pointer', lineHeight: 1 }}
          >
            ✕
          </button>
        </div>
        <p className="text-gray-600 mb-6">
          {current
            ? `Currently set to ${current}. Enter a new address to change your location.`
            : 'Enter your address to see the meetings, votes, spending, and debates near you.'}
        </p>
        <AddressLookup
          onLocationFound={(loc) => {
            onPicked(loc)
            onClose()
          }}
        />
      </div>
    </div>
  )
}
