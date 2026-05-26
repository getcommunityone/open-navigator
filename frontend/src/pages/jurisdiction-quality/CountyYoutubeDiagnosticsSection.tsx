import { Fragment, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchYoutubeChannelDiagnostics,
  type YoutubeChannelDiagnosticsRow,
  type YoutubeDiagnosticsEntity,
} from '../../api/jurisdictionMappingYoutubeDiagnostics'
import { US_STATE_NAMES } from '../../utils/stateMapping'
import { formatCompactNumber, formatFullNumber } from '../../utils/formatCompact'

const GA_FOCUS_COUNTIES = ['DeKalb', 'Fulton', 'Gwinnett']

const REASON_STYLES: Record<string, string> = {
  golden_channel_has_videos: 'text-[var(--jmq-green)]',
  golden_channel_no_bronze_videos: 'text-[#9a6700]',
  verified_candidates_not_promoted: 'text-[#9a6700]',
  candidates_not_verified: 'text-[var(--jmq-red)]',
  no_channel_discovered: 'text-[var(--jmq-red)]',
}

function fmt(n: number): string {
  return formatCompactNumber(n)
}

function fmtTitle(n: number): string | undefined {
  return formatFullNumber(n)
}

function entityForDashboard(entity: string): YoutubeDiagnosticsEntity | null {
  if (entity === 'counties' || entity === 'cities' || entity === 'towns') return entity
  return null
}

function matchesFocusCounty(name: string): boolean {
  const n = name.toLowerCase()
  return GA_FOCUS_COUNTIES.some((c) => n.includes(c.toLowerCase()))
}

function PrimaryWebsiteLink({ url }: { url: string | null | undefined }) {
  const href = url?.trim()
  if (!href) {
    return <span className="text-[var(--jmq-text-muted)]">—</span>
  }
  const display = href.replace(/^https?:\/\//, '')
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      title={href}
      className="line-clamp-2 break-all text-[var(--jmq-teal)] underline-offset-2 hover:underline"
      onClick={(e) => e.stopPropagation()}
    >
      {display}
    </a>
  )
}

function ChannelList({
  title,
  rows,
}: {
  title: string
  rows: { youtube_channel_url?: string | null; channel_title?: string | null; extra?: string }[]
}) {
  if (!rows.length) return null
  return (
    <div className="mt-2">
      <div className="font-mono text-[10px] font-semibold uppercase text-[var(--jmq-text-muted)]">{title}</div>
      <ul className="mt-1 space-y-1">
        {rows.map((ch, i) => (
          <li key={i} className="text-[10px] leading-snug text-[var(--jmq-text-muted)]">
            {ch.channel_title ? <span className="text-[var(--jmq-text)]">{ch.channel_title}</span> : null}
            {ch.channel_title && ch.youtube_channel_url ? ' · ' : null}
            {ch.youtube_channel_url ? (
              <a
                href={ch.youtube_channel_url}
                target="_blank"
                rel="noreferrer"
                className="break-all text-[var(--jmq-teal)] underline-offset-2 hover:underline"
              >
                {ch.youtube_channel_url}
              </a>
            ) : (
              '—'
            )}
            {ch.extra ? <span className="ml-1 text-[var(--jmq-text-muted)]">({ch.extra})</span> : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

function DiagnosticsRowDetail({ row }: { row: YoutubeChannelDiagnosticsRow }) {
  return (
    <div className="border-t border-[var(--jmq-border)]/60 bg-[var(--jmq-surface2)] px-3 py-3 text-xs">
      <p className="leading-relaxed text-[var(--jmq-text)]">{row.gap_reason_label}</p>
      <div className="mt-2 font-mono text-[10px] text-[var(--jmq-text-muted)]">
        <code>{row.jurisdiction_id}</code>
        {row.geoid ? (
          <>
            {' '}
            · GEOID <code>{row.geoid}</code>
          </>
        ) : null}
      </div>
      {row.primary_website_url ? (
        <p className="mt-2 break-all font-mono text-[10px]">
          Website:{' '}
          <a href={row.primary_website_url} target="_blank" rel="noreferrer" className="text-[var(--jmq-teal)]">
            {row.primary_website_url}
          </a>
        </p>
      ) : (
        <p className="mt-2 text-[var(--jmq-text-muted)]">No primary website mapped.</p>
      )}
      <ChannelList
        title="YouTube channel · intermediate.int_events_channels"
        rows={(row.golden_channels ?? []).map((g) => ({
          youtube_channel_url: g.youtube_channel_url,
          channel_title: g.channel_title,
          extra: [g.is_primary ? 'primary' : null, g.discovery_method].filter(Boolean).join(', '),
        }))}
      />
      <ChannelList
        title="Candidates · int_events_channels_candidates"
        rows={(row.candidate_channels ?? []).map((c) => ({
          youtube_channel_url: c.youtube_channel_url,
          channel_title: c.channel_title,
          extra: [
            c.is_verified ? 'verified' : 'unverified',
            c.discovery_method,
            c.rejection_reason,
          ]
            .filter(Boolean)
            .join(', '),
        }))}
      />
    </div>
  )
}

export default function CountyYoutubeDiagnosticsSection({
  entity,
  stateFilter,
  onPickState,
}: {
  entity: string
  stateFilter: string
  onPickState: (code: string) => void
}) {
  const diagEntity = entityForDashboard(entity)
  const [search, setSearch] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [onlyGaps, setOnlyGaps] = useState(true)

  const effectiveState = stateFilter.trim().toUpperCase() || 'GA'
  const effectiveSearch = search.trim()

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['youtube-channel-diagnostics', diagEntity, effectiveState, effectiveSearch],
    queryFn: ({ signal }) =>
      fetchYoutubeChannelDiagnostics(
        {
          entity: diagEntity!,
          state_code: effectiveState,
          name_search: effectiveSearch || undefined,
          limit: 500,
        },
        signal,
      ),
    enabled: !!diagEntity,
    staleTime: 60_000,
  })

  const rows = useMemo(() => {
    const all = data?.rows ?? []
    let list = all
    if (onlyGaps) {
      list = all.filter((r) => r.gap_reason_code !== 'golden_channel_has_videos')
      // GA focus counties stay visible when healthy (channel + bronze videos).
      if (effectiveState === 'GA' && !effectiveSearch) {
        const focusOk = all.filter(
          (r) =>
            matchesFocusCounty(r.name) && r.gap_reason_code === 'golden_channel_has_videos',
        )
        const focusIds = new Set(focusOk.map((r) => r.jurisdiction_id))
        list = [...focusOk, ...list.filter((r) => !focusIds.has(r.jurisdiction_id))]
      }
    }
    if (effectiveState === 'GA' && !effectiveSearch) {
      const focus = list.filter((r) => matchesFocusCounty(r.name))
      const rest = list.filter((r) => !matchesFocusCounty(r.name))
      return [...focus, ...rest]
    }
    return list
  }, [data?.rows, onlyGaps, effectiveState, effectiveSearch])

  const summary = useMemo(() => {
    const all = data?.rows ?? []
    return {
      total: all.length,
      golden: all.filter((r) => r.has_youtube_channel).length,
      bronze: all.filter((r) => r.n_bronze_videos > 0).length,
      noGolden: all.filter((r) => !r.has_youtube_channel).length,
      channelNoBronze: all.filter((r) => r.gap_reason_code === 'golden_channel_no_bronze_videos').length,
    }
  }, [data?.rows])

  if (!diagEntity) return null

  return (
    <div id="jmq-youtube-channel-diagnostics" className="scroll-mt-24 space-y-4">
      <div className="jmq-card">
        <div className="jmq-card-title">YouTube channel diagnostics · {diagEntity}</div>
        <p className="jmq-card-sub">
          <strong>Website</strong> = primary portal from <code>jurisdiction_mapping_analysis</code>.{' '}
          <strong>YouTube channel</strong> = non-blank <code>youtube_channel_url</code> in{' '}
          <code>intermediate.int_events_channels</code> (not <code>website_url</code>). Rows are matched by{' '}
          <code>jurisdiction_id</code> or Census GEOID suffix (e.g. <code>cobb_13067</code> ↔{' '}
          <code>county_13067</code>). Also shows <code>int_events_channels_candidates</code> and bronze video counts.
        </p>
        {entity === 'counties' && effectiveState === 'GA' ? (
          <p className="mt-2 text-sm text-[var(--jmq-text)]">
            <span className="font-semibold text-[var(--jmq-teal)]">Georgia focus: </span>
            {GA_FOCUS_COUNTIES.join(', ')} counties are pinned to the top when no name filter is set.
            With <strong>Hide OK rows</strong>, focus counties still appear when they have a channel and bronze
            videos (e.g. DeKalb).
          </p>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="font-mono text-[10px] uppercase text-[var(--jmq-text-muted)]">
          State
          <select
            className="ml-2 rounded border border-[var(--jmq-border)] bg-white px-2 py-1 text-xs"
            value={effectiveState}
            onChange={(e) => onPickState(e.target.value)}
          >
            {!stateFilter ? <option value="GA">GA (suggested)</option> : null}
            {Object.entries(US_STATE_NAMES).map(([code, name]) => (
              <option key={code} value={code}>
                {code} — {name}
              </option>
            ))}
          </select>
        </label>
        <input
          type="search"
          placeholder="Filter by name (e.g. dekalb)"
          className="min-w-[12rem] flex-1 rounded border border-[var(--jmq-border)] px-2 py-1 text-xs"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <label className="flex items-center gap-1.5 font-mono text-[10px] text-[var(--jmq-text-muted)]">
          <input
            type="checkbox"
            checked={onlyGaps}
            onChange={(e) => setOnlyGaps(e.target.checked)}
          />
          Hide OK rows
        </label>
        {!stateFilter ? (
          <span className="font-mono text-[10px] text-[#9a6700]">
            Tip: set State filter above to scope KPIs; diagnostics default to GA until you pick a state.
          </span>
        ) : null}
      </div>

      {isPending ? (
        <div className="jmq-placeholder">Loading YouTube diagnostics…</div>
      ) : isError ? (
        <div className="jmq-placeholder text-[var(--jmq-red)]">
          Could not load diagnostics: {(error as Error)?.message ?? 'unknown'}. Is the API on port 8000?
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            {(
              [
                { label: `${effectiveState} ${diagEntity}`, n: summary.total },
                { label: 'YouTube channel', n: summary.golden },
                { label: 'Bronze videos', n: summary.bronze },
                { label: 'No YouTube channel', n: summary.noGolden },
                { label: 'Channel, no bronze', n: summary.channelNoBronze },
              ] as const
            ).map((k) => (
              <div
                key={k.label}
                className="rounded-lg border border-[var(--jmq-border)] bg-[var(--jmq-surface2)] px-3 py-2"
              >
                <div className="font-mono text-[10px] font-semibold uppercase text-[var(--jmq-text-muted)]">
                  {k.label}
                </div>
                <div className="mt-1 font-mono text-sm font-bold" title={fmtTitle(k.n)}>
                  {fmt(k.n)}
                </div>
              </div>
            ))}
          </div>

          <div className="overflow-hidden rounded-lg border border-[var(--jmq-border)] bg-[var(--jmq-surface)]">
            <table className="w-full border-collapse text-xs">
              <thead className="bg-[var(--jmq-surface2)]">
                <tr>
                  {[
                    'County / jurisdiction',
                    'Website',
                    'YouTube channel',
                    'Candidates',
                    'Bronze videos',
                    'Why videos missing',
                  ].map(
                    (h) => (
                      <th
                        key={h}
                        className="border-b border-[var(--jmq-border)] px-3 py-2 text-left font-mono text-[10px] font-semibold uppercase tracking-wide text-[var(--jmq-text-muted)]"
                      >
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-3 py-8 text-center text-[var(--jmq-text-muted)]">
                      No rows match this filter.
                    </td>
                  </tr>
                ) : (
                  rows.map((r) => {
                    const focus = effectiveState === 'GA' && matchesFocusCounty(r.name)
                    const open = expandedId === r.jurisdiction_id
                    return (
                      <Fragment key={r.jurisdiction_id}>
                        <tr
                          className={`cursor-pointer border-b border-[var(--jmq-border)]/60 hover:bg-[var(--jmq-surface2)] ${
                            focus ? 'bg-[var(--jmq-teal-dim)]/40' : ''
                          }`}
                          onClick={() => setExpandedId(open ? null : r.jurisdiction_id)}
                        >
                          <td className="px-3 py-2">
                            <div className="font-medium text-[var(--jmq-text)]">
                              {r.name}
                              {focus ? (
                                <span className="ml-2 rounded bg-[var(--jmq-teal)]/15 px-1.5 py-0.5 font-mono text-[9px] text-[var(--jmq-teal)]">
                                  GA focus
                                </span>
                              ) : null}
                            </div>
                            <div className="font-mono text-[10px] text-[var(--jmq-text-muted)]">{r.geoid ?? '—'}</div>
                          </td>
                          <td className="max-w-[14rem] px-3 py-2 font-mono text-[10px]">
                            <PrimaryWebsiteLink url={r.primary_website_url} />
                          </td>
                          <td className="px-3 py-2">
                            {r.has_youtube_channel ? (
                              <span className="text-[var(--jmq-green)]">Yes</span>
                            ) : (
                              <span className="text-[var(--jmq-red)]">No</span>
                            )}
                            {r.n_golden_channel_rows > 1 ? (
                              <span className="ml-1 font-mono text-[10px] text-[var(--jmq-text-muted)]">
                                ({r.n_golden_channel_rows})
                              </span>
                            ) : null}
                          </td>
                          <td className="px-3 py-2 font-mono">
                            {r.n_candidates === 0 ? (
                              '—'
                            ) : (
                              <>
                                {r.n_candidates}
                                {r.n_verified_candidates > 0 ? (
                                  <span className="text-[var(--jmq-green)]"> · {r.n_verified_candidates} ver.</span>
                                ) : null}
                              </>
                            )}
                          </td>
                          <td className="px-3 py-2 font-mono" title={fmtTitle(r.n_bronze_videos)}>
                            {fmt(r.n_bronze_videos)}
                          </td>
                          <td className={`px-3 py-2 ${REASON_STYLES[r.gap_reason_code] ?? ''}`}>
                            <span className="line-clamp-2">{r.gap_reason_label}</span>
                          </td>
                        </tr>
                        {open ? (
                          <tr>
                            <td colSpan={6} className="p-0">
                              <DiagnosticsRowDetail row={r} />
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
          <p className="font-mono text-[10px] text-[var(--jmq-text-muted)]">
            <code>GET /api/jurisdiction-mapping/youtube-channel-diagnostics</code> · {fmt(data?.total ?? 0)} in state
            · click a row for channel URLs
          </p>
        </>
      )}
    </div>
  )
}
