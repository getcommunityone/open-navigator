import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import FollowTheMoney from './FollowTheMoney'

// Money Moves — compact home-page teaser. Shows a single honest one-line
// summary (real headline figure from GET /api/money-flow) and drills down into
// the full tabbed Sankey (<FollowTheMoney>) in a modal. The summary and the
// modal share react-query's cache via the SAME queryKey FollowTheMoney uses, so
// opening the drill-down is instant and never double-fetches.

interface FlowLens {
  head_amount: string
  head_label: string
  count_label: string
  placeholder: boolean
}
interface MoneyFlowResp {
  location_label: string
  lenses: { spending: FlowLens; grants: FlowLens; economy: FlowLens; government: FlowLens }
}

export interface MoneyMovesTeaserProps {
  stateCode?: string
  city?: string
  county?: string
  national?: boolean
  window?: string
  placeLabel: string
}

export default function MoneyMovesTeaser({
  stateCode,
  city,
  county,
  national = false,
  window: win,
  placeLabel,
}: MoneyMovesTeaserProps) {
  const [open, setOpen] = useState(false)

  const scopedState = national ? undefined : stateCode || undefined
  const scopedCity = national ? undefined : city || undefined
  const scopedCounty = national ? undefined : county || undefined
  // Mirror FollowTheMoney's window normalization so the queryKey matches exactly.
  const w = win && win !== 'auto' && win !== 'all' ? win : undefined

  // Same queryKey shape as FollowTheMoney → shared cache, no extra request.
  const { data, isLoading } = useQuery({
    queryKey: ['money-flow', national, scopedState, scopedCity, scopedCounty, undefined, w],
    queryFn: () =>
      api
        .get('/money-flow', {
          params: { state: scopedState, city: scopedCity, county: scopedCounty, q: undefined, window: w },
        })
        .then((r) => r.data as MoneyFlowResp),
    staleTime: 5 * 60 * 1000,
  })

  // Lead with the lens FollowTheMoney opens on: the resident's own tax dollars
  // (Government budget) when a location is known, else Public spending.
  const leadKey = stateCode && !national ? 'government' : 'spending'
  const lens = data?.lenses[leadKey]
  const hasData = !!lens && !lens.placeholder

  // Close on Escape while the drill-down is open.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  return (
    <>
      {/* One-line summary — light, real headline figure, drill-down on the right. */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
          background: '#fff',
          border: '1px solid #e7e5e4',
          borderRadius: 14,
          padding: '14px 16px',
        }}
      >
        <span style={{ fontSize: 20, lineHeight: 1 }}>💵</span>
        <div style={{ flex: 1, minWidth: 0, fontSize: 14, color: '#57534e', lineHeight: 1.4 }}>
          <span style={{ fontWeight: 700, color: '#059669' }}>Money Moves</span>
          {isLoading ? (
            <span style={{ color: '#a8a29e' }}> · loading…</span>
          ) : hasData ? (
            <>
              {' · '}
              <b style={{ color: '#0f2b2b' }}>{lens!.head_amount}</b> {lens!.head_label}
              <span style={{ color: '#a8a29e' }}> · {lens!.count_label}</span>
              <span style={{ color: '#78716c' }}> · 📍 {placeLabel}</span>
            </>
          ) : (
            <span style={{ color: '#78716c' }}> · No money flows traced for {placeLabel} yet</span>
          )}
        </div>
        {hasData && (
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="font-display"
            style={{
              flexShrink: 0,
              fontSize: 14,
              fontWeight: 700,
              color: '#059669',
              background: '#ecfdf5',
              border: '1px solid #a7f3d0',
              borderRadius: 999,
              padding: '7px 16px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            Explore the flows →
          </button>
        )}
      </div>

      {/* Drill-down modal hosting the full tabbed Sankey. */}
      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Money Moves — follow the money"
          onClick={() => setOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 60,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'center',
            padding: '5vh 16px',
            overflowY: 'auto',
            animation: 'fadeIn 150ms ease-out',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              position: 'relative',
              width: '100%',
              maxWidth: 920,
              background: '#faf9f7',
              borderRadius: 18,
              padding: '20px 20px 24px',
              boxShadow: '0 24px 60px rgba(0,0,0,0.28)',
            }}
          >
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close"
              style={{
                position: 'absolute',
                top: 12,
                right: 12,
                width: 32,
                height: 32,
                borderRadius: 999,
                border: '1px solid #e7e5e4',
                background: '#fff',
                color: '#57534e',
                fontSize: 18,
                lineHeight: 1,
                cursor: 'pointer',
              }}
            >
              ×
            </button>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 14, paddingRight: 36 }}>
              <span style={{ fontSize: 20 }}>💵</span>
              <h2 className="font-display" style={{ fontSize: 22, fontWeight: 700, margin: 0, color: '#059669' }}>
                Money Moves
              </h2>
              <span style={{ fontSize: 14, color: '#78716c' }}>
                Follow the dollars — every flow traced to the record · 📍 {placeLabel}
              </span>
            </div>
            <FollowTheMoney
              embedded
              national={national}
              stateCode={stateCode}
              city={city}
              county={county}
              window={win}
            />
          </div>
        </div>
      )}
    </>
  )
}
