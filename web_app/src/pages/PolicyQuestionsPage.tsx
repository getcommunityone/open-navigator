import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  fetchPolicyQuestions,
  fetchPolicyQuestion,
  type PolicyQuestionSummary,
  type PolicyQuestionDetail,
  type QuestionTrendPoint,
} from '../api/policyQuestions'
import MeetingCardList from '../components/MeetingCardList'

// ────────────────────────────────────────────────────────────────────────────
// Questions That Keep Coming Up — the policy-question registry with Money & Talk.
// Ported from the design prototype, but EVERY figure is REAL (CLAUDE.md: No
// Fabricated Data):
//   • approval, category, instances        → /api/policy-question (rollup mart)
//   • Money & Talk bars + tags             → money_total / money_share / talk_share
//                                            (item_interestingness.net_dollar_impact)
//   • "the last four years" trend          → /api/policy-question/{id}.trend
//                                            (policy_question_trend mart, by quarter)
//   • case for / against, recent instances → question detail (arguments + instances)
// The prototype's invented dollars/minutes/quarterly series are all dropped.
// ────────────────────────────────────────────────────────────────────────────

const SPEND_COLOR = '#0d9488' // teal — money
const TALK_COLOR = '#d97706' // amber — talk / how often

const fmtMoney = (v: number) =>
  v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B`
  : v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M`
  : v >= 1e3 ? `$${Math.round(v / 1e3)}K`
  : `$${Math.round(v)}`

const MONO = "'IBM Plex Mono', monospace"

// "2024-04-01" → "Q2'24"
const quarterLabel = (iso: string) => {
  const d = new Date(iso)
  const q = Math.floor(d.getUTCMonth() / 3) + 1
  return `Q${q}'${String(d.getUTCFullYear()).slice(2)}`
}

type SortKey = 'contested' | 'frequent'
type LevelScope = 'all' | 'local' | 'state'
const MIN_VOTES = 3 // min jurisdictions before a contested ranking is meaningful

export default function PolicyQuestionsPage() {
  const navigate = useNavigate()
  const [open, setOpen] = useState<Set<string>>(new Set())
  const [levelScope, setLevelScope] = useState<LevelScope>('all')
  const [sortBy, setSortBy] = useState<SortKey>('contested')
  const [panelOpen, setPanelOpen] = useState(false)
  const [selectedCats, setSelectedCats] = useState<Set<string> | null>(null) // null = all

  // For now we focus the whole site on the curated/pinned "big questions" only,
  // so this registry page lists the featured set instead of the full clustered
  // registry. Swap back to { limit: 200 } to restore the full list.
  const { data, isLoading } = useQuery<PolicyQuestionSummary[]>({
    queryKey: ['policy-questions-registry', 'featured'],
    queryFn: () => fetchPolicyQuestions({ featured: true }),
  })
  const ALL = useMemo(() => data ?? [], [data])

  const CATEGORIES = useMemo(
    () => [...new Set(ALL.map((q) => q.primary_theme).filter((c): c is string => !!c && c !== '__unthemed__'))].sort(),
    [ALL],
  )
  const catsActive = selectedCats ?? new Set(CATEGORIES)

  const toggleCat = (c: string) =>
    setSelectedCats(() => {
      const next = new Set(catsActive)
      if (next.has(c)) {
        if (next.size > 1) next.delete(c)
      } else next.add(c)
      return next
    })

  const inScope = (q: PolicyQuestionSummary) =>
    levelScope === 'all' || (q.scope ?? 'local') === levelScope

  const rate = (q: PolicyQuestionSummary) =>
    q.jurisdictions_total > 0 ? (q.jurisdictions_approved / q.jurisdictions_total) * 100 : null

  const rows = useMemo(() => {
    const arr = ALL.filter((q) => inScope(q) && (!q.primary_theme || catsActive.has(q.primary_theme)))
    if (sortBy === 'frequent') {
      arr.sort((a, b) => b.instances_total - a.instances_total)
    } else {
      // Most contested: closest to a 50/50 split, among questions with enough reach.
      arr.sort((a, b) => {
        const av = a.jurisdictions_total >= MIN_VOTES
        const bv = b.jurisdictions_total >= MIN_VOTES
        if (av && bv) return Math.abs((rate(a) ?? 50) - 50) - Math.abs((rate(b) ?? 50) - 50)
        if (av !== bv) return av ? -1 : 1
        return b.instances_total - a.instances_total
      })
    }
    return arr
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ALL, levelScope, sortBy, selectedCats])

  // Tag from real shares: a question that moves big money with little relative
  // discussion, or vice-versa. Shares are already percentages of all decisions.
  const tagOf = (q: PolicyQuestionSummary): 'quiet-money' | 'hot-topic' | null => {
    const m = q.money_share ?? 0
    const t = q.talk_share ?? 0
    if (m >= 2 * t && m >= 1.5) return 'quiet-money'
    if (t >= 2 * m && t >= 1.5) return 'hot-topic'
    return null
  }

  const toggle = (id: string) =>
    setOpen((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  return (
    <div className="min-h-screen bg-stone-50 p-6" style={{ fontFamily: "'Source Sans 3', sans-serif" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
@keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }`}</style>

      <div className="max-w-3xl mx-auto">
        <button
          type="button"
          onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/'))}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-stone-500 hover:text-stone-900 mb-4"
        >
          <span aria-hidden="true">←</span> Back
        </button>
        <div className="text-[11px] uppercase tracking-widest text-stone-500 mb-1" style={{ fontFamily: MONO }}>
          Policy question registry
        </div>
        <h1 className="text-3xl text-stone-800" style={{ fontFamily: "'Playfair Display', serif", fontWeight: 700 }}>
          Questions That Keep Coming Up
        </h1>
        <p className="text-sm text-stone-500 mt-1 mb-4 max-w-xl">
          Recurring choices that local governments (and, soon, state legislatures) face — with how
          they usually go, the arguments on each side, and what each question moves in real dollars
          and how often it comes up.
        </p>

        {/* Filter bar */}
        <div className="flex items-center gap-2 flex-wrap mb-4">
          <button
            onClick={() => setPanelOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-stone-300 bg-white text-xs uppercase tracking-wider text-stone-600 hover:border-teal-600 hover:text-teal-700 transition-colors"
            style={{ fontFamily: MONO }}
          >
            ☰ Categories
            <span className="px-1.5 py-0.5 rounded-full bg-teal-600 text-white text-[10px]">{catsActive.size}</span>
          </button>
          <div className="flex rounded-md border border-stone-300 overflow-hidden text-xs" style={{ fontFamily: MONO }}>
            {([['local', 'Local'], ['state', 'State'], ['all', 'All']] as [LevelScope, string][]).map(([l, label]) => (
              <button
                key={l}
                onClick={() => setLevelScope(l)}
                className={`px-3 py-1.5 uppercase tracking-wider transition-colors ${
                  levelScope === l ? 'bg-teal-600 text-white' : 'bg-white text-stone-500 hover:bg-stone-100'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="flex rounded-md border border-stone-300 overflow-hidden text-xs" style={{ fontFamily: MONO }}>
            {([['contested', 'Most contested'], ['frequent', 'Most frequent']] as [SortKey, string][]).map(([s, label]) => (
              <button
                key={s}
                onClick={() => setSortBy(s)}
                className={`px-3 py-1.5 uppercase tracking-wider transition-colors ${
                  sortBy === s ? 'bg-stone-700 text-white' : 'bg-white text-stone-500 hover:bg-stone-100'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600 my-10" />
        ) : (
          <div className="space-y-2">
            {rows.map((q) => {
              const isOpen = open.has(q.question_id)
              const r = rate(q)
              const tag = tagOf(q)
              const mShare = q.money_share ?? 0
              const tShare = q.talk_share ?? 0
              const maxS = Math.max(mShare, tShare, 1)
              return (
                <div key={q.question_id} className="bg-white rounded-lg border border-stone-200 shadow-sm overflow-hidden">
                  <button onClick={() => toggle(q.question_id)} className="w-full text-left px-4 py-3 hover:bg-stone-50/60 transition-colors">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-stone-800 leading-snug">{q.canonical_text}</div>
                        <div className="flex items-center gap-2 mt-1.5 flex-wrap text-xs" style={{ fontFamily: MONO }}>
                          {r != null && (
                            <>
                              <span className="text-teal-700 font-semibold">
                                {q.jurisdictions_approved}/{q.jurisdictions_total} approved ({r.toFixed(0)}%)
                              </span>
                              <span className="text-stone-300">·</span>
                            </>
                          )}
                          {q.primary_theme && q.primary_theme !== '__unthemed__' && (
                            <span className="text-stone-500 uppercase tracking-wide">{q.primary_theme}</span>
                          )}
                          {levelScope === 'all' && q.scope && (
                            <span className="px-1.5 rounded bg-stone-100 text-stone-600">{q.scope}</span>
                          )}
                          <span className="text-stone-300">·</span>
                          <span className="text-stone-500">{q.instances_total} instances</span>
                          {tag === 'quiet-money' && (
                            <span className="px-2 py-0.5 rounded-full bg-violet-50 border border-violet-200 text-violet-800 normal-case tracking-normal" style={{ fontFamily: "'Source Sans 3', sans-serif" }}>
                              Big money, little discussion
                            </span>
                          )}
                          {tag === 'hot-topic' && (
                            <span className="px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200 text-amber-800 normal-case tracking-normal" style={{ fontFamily: "'Source Sans 3', sans-serif" }}>
                              Comes up a lot, smaller money
                            </span>
                          )}
                        </div>
                      </div>
                      <span className="text-stone-300 text-sm shrink-0">{isOpen ? '▾' : '▸'}</span>
                    </div>
                  </button>

                  {isOpen && (
                    <div className="px-4 pb-4 border-t border-stone-100">
                      {/* Money & talk — REAL shares of all decisions */}
                      <div className="rounded-md bg-stone-50 border border-stone-100 px-3 py-2.5 mt-3 mb-4">
                        <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
                          <span className="text-[10px] uppercase tracking-widest text-stone-500" style={{ fontFamily: MONO }}>
                            Money &amp; talk · share of all decisions
                          </span>
                          <span className="text-[11px] text-stone-500" style={{ fontFamily: MONO }}>
                            {fmtMoney(q.money_total ?? 0)} moved · came up {q.instances_total}×
                          </span>
                        </div>
                        <div className="grid items-center gap-x-2 gap-y-1" style={{ gridTemplateColumns: '3.5rem minmax(0,1fr) 2.8rem' }}>
                          <span className="text-[10px] uppercase tracking-wider text-stone-500" style={{ fontFamily: MONO }}>Money</span>
                          <div className="h-3 bg-stone-200/60 rounded-sm overflow-hidden">
                            <div className="h-full rounded-sm" style={{ width: `${Math.max(1.5, (mShare / maxS) * 100)}%`, background: SPEND_COLOR }} />
                          </div>
                          <span className="text-xs text-stone-500 text-right" style={{ fontFamily: MONO }}>{mShare.toFixed(1)}%</span>
                          <span className="text-[10px] uppercase tracking-wider text-stone-500" style={{ fontFamily: MONO }}>Talk</span>
                          <div className="h-3 bg-stone-200/60 rounded-sm overflow-hidden">
                            <div className="h-full rounded-sm" style={{ width: `${Math.max(1.5, (tShare / maxS) * 100)}%`, background: TALK_COLOR }} />
                          </div>
                          <span className="text-xs text-stone-500 text-right" style={{ fontFamily: MONO }}>{tShare.toFixed(1)}%</span>
                        </div>
                      </div>

                      {/* Arguments + trend + instances — lazily fetched detail */}
                      <Drilldown questionId={q.question_id} />
                    </div>
                  )}
                </div>
              )
            })}
            {rows.length === 0 && (
              <div className="text-sm text-stone-400 py-6 text-center">No questions match the current filters.</div>
            )}
          </div>
        )}

        {/* Categories flyout */}
        {panelOpen && (
          <>
            <div className="fixed inset-0 bg-stone-900/30 z-40" style={{ animation: 'fadeIn 150ms ease' }} onClick={() => setPanelOpen(false)} />
            <div className="fixed top-0 right-0 h-full w-80 max-w-[85vw] bg-white z-50 shadow-2xl border-l border-stone-200 flex flex-col" style={{ animation: 'slideIn 200ms cubic-bezier(0.4, 0, 0.2, 1)' }}>
              <div className="flex items-center justify-between px-4 py-3 border-b border-stone-200">
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-stone-500" style={{ fontFamily: MONO }}>
                    {catsActive.size} selected
                  </div>
                  <div className="text-base text-stone-800" style={{ fontFamily: "'Playfair Display', serif", fontWeight: 600 }}>
                    Categories
                  </div>
                </div>
                <button onClick={() => setPanelOpen(false)} className="w-8 h-8 rounded-md hover:bg-stone-100 text-stone-400 hover:text-stone-600" aria-label="Close">✕</button>
              </div>
              <div className="flex-1 overflow-auto p-2">
                {CATEGORIES.map((c) => {
                  const on = catsActive.has(c)
                  const count = ALL.filter((q) => q.primary_theme === c && inScope(q)).length
                  return (
                    <button
                      key={c}
                      onClick={() => toggleCat(c)}
                      className={`w-full flex items-center gap-1.5 px-2 py-2 rounded text-xs text-left transition-colors ${
                        on ? 'bg-teal-50/70 text-stone-800' : 'text-stone-600 hover:bg-stone-50'
                      }`}
                    >
                      <span
                        className="w-3.5 h-3.5 shrink-0 rounded-sm border flex items-center justify-center text-[9px] text-white"
                        style={{ background: on ? '#0d9488' : 'transparent', borderColor: on ? '#0d9488' : '#d6d3d1' }}
                      >
                        {on ? '✓' : ''}
                      </span>
                      <span className="flex-1">{c}</span>
                      <span className="text-stone-400" style={{ fontFamily: MONO }}>{count}</span>
                    </button>
                  )
                })}
              </div>
              <div className="p-3 border-t border-stone-200">
                <button onClick={() => setPanelOpen(false)} className="w-full py-2 rounded-md bg-teal-600 text-white text-sm font-semibold hover:bg-teal-700 transition-colors">
                  Done · {catsActive.size} selected
                </button>
              </div>
            </div>
          </>
        )}

        <p className="text-xs text-stone-400 mt-3" style={{ fontFamily: MONO }}>
          Money and talk shares are of all decisions, not just listed questions.
        </p>
      </div>
    </div>
  )
}

// ── Drill-down: arguments + 4-year trend + recent instances (lazily fetched) ──
function Drilldown({ questionId }: { questionId: string }) {
  const { data: q, isLoading } = useQuery<PolicyQuestionDetail>({
    queryKey: ['policy-question-detail', questionId],
    queryFn: () => fetchPolicyQuestion(questionId),
    staleTime: 5 * 60 * 1000,
  })

  if (isLoading || !q) {
    return <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-teal-600 my-3" />
  }

  const pros = q.arguments.filter((a) => a.stance === 'pro')
  const cons = q.arguments.filter((a) => a.stance === 'con')

  return (
    <>
      {(pros.length > 0 || cons.length > 0) && (
        <div className="grid sm:grid-cols-2 gap-4 mb-4">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-teal-700 mb-1.5" style={{ fontFamily: MONO }}>
              The case for
            </div>
            {pros.length ? (
              pros.map((a) => (
                <p key={a.argument_id} className="text-sm text-stone-600 mb-1.5 leading-snug">— {a.label || a.summary}</p>
              ))
            ) : (
              <p className="text-sm text-stone-400">No arguments captured yet.</p>
            )}
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-widest text-rose-700 mb-1.5" style={{ fontFamily: MONO }}>
              The case against
            </div>
            {cons.length ? (
              cons.map((a) => (
                <p key={a.argument_id} className="text-sm text-stone-600 mb-1.5 leading-snug">— {a.label || a.summary}</p>
              ))
            ) : (
              <p className="text-sm text-stone-400">No arguments captured yet.</p>
            )}
          </div>
        </div>
      )}

      {/* The last four years — real quarterly money line + instance bars */}
      {q.trend.length > 0 && (
        <div className="rounded-md bg-stone-50 border border-stone-100 px-3 py-2.5 mb-4">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
            <span className="text-[10px] uppercase tracking-widest text-stone-500" style={{ fontFamily: MONO }}>
              By quarter
            </span>
            <span className="flex items-center gap-3 text-[11px] text-stone-500">
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: SPEND_COLOR }} />money</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: TALK_COLOR }} />how often</span>
            </span>
          </div>
          <Trend points={q.trend} />
        </div>
      )}

      {/* Recent instances — real decisions/bills that instantiate the question */}
      {q.sample_instances.length > 0 && (
        <>
          <div className="text-[10px] uppercase tracking-widest text-stone-500 mb-1.5" style={{ fontFamily: MONO }}>
            Recent instances
          </div>
          {q.sample_instances.slice(0, 6).map((ex) => (
            <div key={ex.instance_id} className="flex items-start justify-between gap-3 py-1.5 text-sm">
              <div className="min-w-0">
                <span className="text-stone-700">
                  {[ex.city || ex.jurisdiction_name, ex.state_code].filter(Boolean).join(', ') || 'Unknown jurisdiction'}
                </span>
                {ex.occurred_at && (
                  <span className="text-xs text-stone-400 ml-2">{new Date(ex.occurred_at).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}</span>
                )}
              </div>
              {ex.outcome_normalized && (
                <span className="text-xs shrink-0 capitalize" style={{ fontFamily: MONO, color: ex.outcome_normalized === 'approved' || ex.outcome_normalized === 'enacted' ? SPEND_COLOR : '#78716c' }}>
                  {ex.outcome_normalized}
                </span>
              )}
            </div>
          ))}
        </>
      )}

      {/* Meeting-level cards linked to this question, each drilling into its own
          decisions (search + filters). Often sparse — question→meeting links are
          few — which renders an honest empty state, never a fabricated list. */}
      <div className="mt-5 border-t border-stone-100 pt-4">
        <MeetingCardList questionId={questionId} title="Meetings on this question" />
      </div>
    </>
  )
}

// Compact money line + per-quarter instance bars over the real trend points.
function Trend({ points }: { points: QuestionTrendPoint[] }) {
  const w = 560
  const h = 70
  const pad = 4
  const mMax = Math.max(...points.map((p) => p.money), 1) * 1.15
  const px = (i: number) => pad + (points.length <= 1 ? 0 : (i / (points.length - 1)) * (w - pad * 2))
  const py = (v: number) => h - pad - (v / mMax) * (h - pad * 2)
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${px(i).toFixed(1)},${py(p.money).toFixed(1)}`).join('')
  const maxInst = Math.max(...points.map((p) => p.instances), 1)
  const anyMoney = points.some((p) => p.money > 0)

  return (
    <div>
      {anyMoney ? (
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
          <path d={path} fill="none" stroke={SPEND_COLOR} strokeWidth="2" strokeLinejoin="round" />
        </svg>
      ) : (
        <div className="text-[11px] text-stone-400 py-1" style={{ fontFamily: MONO }}>
          No dollar impact recorded for this question (e.g. bills, or non-financial votes).
        </div>
      )}
      <div className="flex items-end gap-[2px] h-6 mt-1">
        {points.map((p) => (
          <div
            key={p.quarter_start}
            className="flex-1 rounded-t-sm"
            style={{ height: `${Math.max(8, (p.instances / maxInst) * 100)}%`, background: TALK_COLOR, opacity: 0.55 }}
            title={`${quarterLabel(p.quarter_start)}: came up ${p.instances}×${p.money > 0 ? `, ${fmtMoney(p.money)}` : ''}`}
          />
        ))}
      </div>
      <div className="flex justify-between text-[9px] text-stone-400 mt-0.5" style={{ fontFamily: MONO }}>
        <span>{quarterLabel(points[0].quarter_start)}</span>
        <span>amber bars: how often it came up</span>
        <span>{quarterLabel(points[points.length - 1].quarter_start)}</span>
      </div>
    </div>
  )
}
