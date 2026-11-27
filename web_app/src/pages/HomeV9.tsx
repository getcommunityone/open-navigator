// Open Navigator — Homepage (v9 prototype design), single-column.
//
// This is a faithful port of the "OpenNavigatorHome (9)" design prototype, but
// EVERY figure is wired to REAL data (CLAUDE.md: No Fabricated Data). The
// prototype's invented numbers — the ZIP→rate table, the $5.7M/8/18 snapshot,
// the hard-coded THIS_WEEK / feed stories, the directory counts — are all
// replaced with live API values, and anything genuinely missing renders an
// honest empty state instead of a placeholder.
//
//   - Money hook + modal  → the real <MoneyHook> (/api/local-finance +
//                           /api/grandkid-outlook + the real ACS property-tax rate).
//   - Snapshot strip      → /api/lenses `activity` (tracked spending, contested,
//                           analyzed, coming-back-for-a-vote).
//   - This week / signals / Close-to-Home feed → /api/lenses `lenses[].cards`.
//   - Browse the directory counts → /search type_totals + policy-question registry.
//   - Trending questions  → real policy-question registry (/api/policy-question/).
//
// Editorial UI copy (signal descriptions, topic labels, "why people use it") is
// kept verbatim from the prototype — that's interface text, not data figures.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { useMediaQuery } from '../hooks/useMediaQuery'
import MoneyGameModal from '../components/MoneyGameModal'
import MoneyMovesTeaser from '../components/MoneyMovesTeaser'
import { useLocation as useLocationContext } from '../contexts/LocationContext'
import LocationPickerDialog from '../components/LocationPickerDialog'
import { PLACE_PICKED_EVENT, usePlacePick } from '../hooks/usePlacePick'
import { useDocumentTitle } from '../utils/useDocumentTitle'
import SiteHeader from '../components/SiteHeader'
import SiteFooter from '../components/SiteFooter'
import { LensCarousel, type ApiCard } from '../components/StoryLenses'
import MeetingThumbnail from '../components/MeetingThumbnail'
import { inferThumbnailKind } from '../lib/youtubeThumbnail'
import { fetchMeetings, type MeetingCard } from '../api/meetings'
import { highlightSnippet } from '../lib/highlight'
import HomeDataStories from '../components/home/HomeDataStories'
import { STATE_CODES } from '../lib/usStates'
import { SEARCH_CATEGORIES, SEARCH_CATEGORY_TYPES, countForCategory, type SearchCategory } from '../lib/searchCategories'

// The brand teal, the same as the data stories' primary action and Tailwind's primary-600 (#975).
const TEAL = '#0f766e'
const TEAL_DARK = '#115e59'
const INK = '#1c1917'

const FONTS = `
.v9 .font-display { font-family: 'Playfair Display', Georgia, serif; }
.v9 .font-body { font-family: 'Source Sans 3', system-ui, sans-serif; }
.v9 .font-mono-x { font-family: 'IBM Plex Mono', monospace; }
.v9 .hide-scroll::-webkit-scrollbar { display: none; }
.v9 .hide-scroll { scrollbar-width: none; }
.v9 .clamp2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.v9 { overflow-x: clip; max-width: 100%; }
.v9 .v9-main { box-sizing: border-box; max-width: 100%; }
.v9 .v9-search { display: flex; min-width: 0; }
.v9 .v9-search:focus-within { outline: 2px solid #0f766e; outline-offset: 2px; }
.v9 .v9-money-hook-text { flex: 1; min-width: 0; }
html { scroll-behavior: smooth; }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.v9 .home-stories { background: #fff; border-bottom: 1px solid #e7e5e4; padding: 28px 24px 30px; }
.v9 .home-stories-inner { max-width: 1180px; margin: 0 auto; }
.v9 .v9-find-town { display: inline-flex; align-items: center; gap: 10px; margin: 20px auto 0; max-width: 760px; padding: 11px 22px; border-radius: 999px; background: rgba(13,148,136,0.08); border: 1px solid rgba(13,148,136,0.3); font: inherit; font-size: 15px; color: #0f766e; line-height: 1.4; cursor: pointer; text-align: left; }
.v9 .v9-find-town:hover { background: rgba(13,148,136,0.14); }
.v9 .v9-find-town:focus-visible { outline: 2px solid #0f766e; outline-offset: 2px; }
.v9 .v9-find-town strong { color: #115e59; }
.v9 .home-story-card { display: grid; grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.2fr); gap: 28px; align-items: start; }
.v9 .home-story-eyebrow { margin: 0; font-size: 11.5px; letter-spacing: .12em; text-transform: uppercase; color: #0f766e; font-weight: 600; }
/* Sized so a three-line title, the subhead and both buttons fit one laptop screen (#1176). */
.v9 .home-story-headline { font-size: clamp(28px, 3.2vw, 46px); font-weight: 800; line-height: 1.08; letter-spacing: -0.015em; margin: 6px 0 10px; color: #1c1917; }
.v9 .home-story-headline.is-long { font-size: clamp(24px, 2.5vw, 36px); line-height: 1.12; }
.v9 .home-story-subhead { margin: 0; font-size: clamp(15px, 1.3vw, 17px); line-height: 1.5; color: #44403c; max-width: 34em; }
.v9 .home-story-basis { margin: 8px 0 0; font-size: 13px; color: #78716c; }
/* Always reachable (owner, 2026-11-26): when the card pushes the buttons below the fold, they stick to the bottom of
   the screen until their own place scrolls into view, then sit there. */
.v9 .home-story-actions { position: sticky; bottom: 0; z-index: 5; padding: 12px 0 calc(12px + env(safe-area-inset-bottom, 0px));
  background: linear-gradient(to top, #fff 78%, rgba(255,255,255,0)); }
.v9 .home-story-drill { margin: 10px 0 0; font-size: 13.5px; color: #57534e; }
.v9 .home-story-drill strong { color: #1c1917; }
.v9 .home-story-map { position: relative; }
/* The map never pushes the card past one screen (#1176): capped by height, kept centred at its aspect ratio. */
.v9 .home-story-map > svg, .v9 .home-story-map svg[role="img"] { max-height: min(60vh, 560px); width: auto; max-width: 100%; margin: 0 auto; }
.v9 .home-map-card { position: absolute; width: min(290px, 70%); background: #fff; border: 1px solid #e7e5e4; border-radius: 12px; box-shadow: 0 10px 28px rgba(28,25,23,.12); padding: 14px 16px; margin: 0; z-index: 2; pointer-events: auto; }
.v9 .home-topics { margin-top: 22px; border: 1px solid #e7e5e4; border-radius: 14px; background: #fff; }
.v9 .home-topics-head { display: flex; align-items: center; justify-content: space-between; padding: 12px 18px 0; }
.v9 .home-topics-head p { margin: 0; font-size: 12px; letter-spacing: .14em; text-transform: uppercase; color: #44403c; font-weight: 600; border-bottom: 2px solid #0f766e; padding-bottom: 8px; }
.v9 .home-topics-all { color: #1c1917; display: inline-flex; padding: 4px; }
.v9 .home-topics-scroller { position: relative; }
.v9 .home-topics-list { list-style: none; margin: 0; padding: 12px; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(230px, 1fr); gap: 0; overflow-x: auto; scroll-snap-type: x mandatory; scroll-padding-inline: 12px; overscroll-behavior-x: contain; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
.v9 .home-topics-list::-webkit-scrollbar { display: none; }
.v9 .home-topics-list li { scroll-snap-align: start; }
.v9 .home-topics-list li + li { border-left: 1px solid #e7e5e4; }
.v9 .home-topics-arrow { position: absolute; top: 50%; transform: translateY(-50%); z-index: 2; width: 38px; height: 38px; border-radius: 50%; border: 1px solid #e7e5e4; background: #fff; color: #1c1917; box-shadow: 0 2px 6px rgba(28,25,23,.12); display: grid; place-items: center; cursor: pointer; padding: 0; transition: opacity .15s; }
.v9 .home-topics-arrow.is-prev { left: 6px; }
.v9 .home-topics-arrow.is-next { right: 6px; }
.v9 .home-topics-arrow:hover:not(:disabled) { background: #f0fdfa; border-color: #0f766e; color: #0f766e; }
.v9 .home-topics-arrow:focus-visible { outline: 2px solid #0f766e; outline-offset: 2px; }
.v9 .home-topics-arrow:disabled { opacity: 0; pointer-events: none; }
.v9 .home-topics-arrow[hidden] { display: none; }
.v9 .home-topics-dots { display: flex; justify-content: center; gap: 4px; padding: 0 12px 12px; }
.v9 .home-topics-dot { width: 24px; height: 24px; padding: 0; border: 0; background: none; cursor: pointer; display: grid; place-items: center; }
.v9 .home-topics-dot::before { content: ''; width: 8px; height: 8px; border-radius: 50%; background: #d6d3d1; transition: background .15s, width .15s; }
.v9 .home-topics-dot.is-on::before { background: #0f766e; width: 20px; border-radius: 999px; }
.v9 .home-topics-dot:focus-visible { outline: 2px solid #0f766e; outline-offset: 1px; border-radius: 999px; }
@media (max-width: 639px) { .v9 .home-topics-arrow { display: none; } }
@media (prefers-reduced-motion: reduce) { .v9 .home-topics-list { scroll-behavior: auto; } .v9 .home-topics-arrow, .v9 .home-topics-dot::before { transition: none; } }
.v9 .home-topic { display: flex; gap: 12px; align-items: flex-start; padding: 10px 14px; text-decoration: none; color: inherit; border-radius: 10px; }
.v9 .home-topic:hover { background: #fafaf9; }
.v9 .home-topic:focus-visible { outline: 3px solid #0f766e; outline-offset: -3px; }
.v9 .home-topics-all:focus-visible { outline: 2px solid #0f766e; outline-offset: 2px; border-radius: 6px; }
.v9 button.home-topic { width: 100%; background: none; border: 0; font: inherit; text-align: left; cursor: pointer; }
.v9 .home-topic.is-on { background: #f0fdfa; box-shadow: inset 0 0 0 2px #0f766e; }
.v9 .home-topic-on { display: inline-block; align-self: flex-start; margin-top: 6px; padding: 2px 8px; border-radius: 999px; background: #0f766e; color: #fff; font-size: 12px; font-weight: 700; }
.v9 .home-topic.is-soon { cursor: default; }
.v9 .home-topic.is-soon:hover { background: none; }
.v9 .home-topic-soon { display: inline-block; align-self: flex-start; margin-top: 6px; padding: 2px 8px; border-radius: 999px; background: #f5f5f4; color: #57534e; font-size: 12px; font-weight: 600; }
.v9 .home-topic-icon { flex: none; width: 58px; height: 58px; border-radius: 50%; display: grid; place-items: center; }
.v9 .home-topic-text { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.v9 .home-topic-title { font-weight: 700; font-size: 15.5px; color: #1c1917; }
.v9 .home-topic-blurb { font-size: 13.5px; color: #57534e; line-height: 1.4; }
.v9 .home-topic-caption { color: #292524; font-weight: 500; }
.v9 .home-topic-ai { font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: #78716c; font-weight: 600; }
.v9 .home-topic-go { font-size: 13.5px; font-weight: 700; color: #0f766e; margin-top: 2px; }
.v9 button.home-topic.is-soon { cursor: pointer; }
.v9 button.home-topic.is-soon:hover { background: #fafaf9; }
.v9 .home-topic.is-picked { background: #fafaf9; box-shadow: inset 0 0 0 2px #a8a29e; }
.v9 .home-topic-companies { border-top: 1px solid #e7e5e4; padding: 14px 18px 16px; }
.v9 .home-topic-companies h3 { margin: 0 0 10px; font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: #44403c; font-weight: 600; }
.v9 .home-topic-companies-note { margin: 8px 0 0; font-size: 13.5px; color: #57534e; }
.v9 .home-topic-companies-list { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.v9 .home-topic-company { border: 1px solid #e7e5e4; border-radius: 12px; padding: 12px 14px; min-width: 0; }
.v9 .home-topic-company-name { margin: 0; font-weight: 700; font-size: 15px; color: #1c1917; }
.v9 .home-topic-company-name a { color: inherit; }
.v9 .home-topic-company-brands { font-weight: 400; font-size: 13px; color: #78716c; }
.v9 .home-topic-company-counts { margin: 4px 0 0; font-size: 13.5px; color: #44403c; }
.v9 .home-topic-company-counts a { color: #0f766e; font-weight: 700; }
.v9 .home-topic-company-quote { margin: 8px 0 0; padding-left: 10px; border-left: 2px solid #0f766e; font-size: 13.5px; font-style: italic; line-height: 1.45; color: #44403c; overflow-wrap: anywhere; }
.v9 .home-topic-company-quote footer { font-style: normal; font-size: 12px; color: #78716c; margin-top: 4px; }
.v9 .home-topic-company-quote a { color: #0f766e; }
@media (max-width: 860px) {
  .v9 .home-story-card { grid-template-columns: minmax(0, 1fr); }
  .v9 .home-map-card { position: static; width: auto; margin-top: 8px; }
  .v9 .home-story-actions { flex-direction: column; }
  .v9 .home-story-actions a { display: block; width: 100%; box-sizing: border-box; }
}
@media (max-width: 760px) {
  .v9 .v9-main { padding-left: 16px !important; padding-right: 16px !important; }
  .v9 .v9-money-hook-text { min-width: 0 !important; }
  .v9 .v9-section-full { padding-left: 16px !important; padding-right: 16px !important; }
  .v9 .v9-footer-inner { padding-left: 16px !important; padding-right: 16px !important; }
  .v9 .v9-money-hook { padding: 14px 16px !important; gap: 12px !important; flex-direction: column !important; align-items: stretch !important; }
  .v9 .v9-money-hook-cta { width: 100%; text-align: center; }
  .v9 .v9-hero { padding-top: 28px !important; }
}
.v9 .v9-browse-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
  justify-content: center;
}
@media (min-width: 900px) {
  .v9 .v9-browse-pills {
    flex-wrap: nowrap;
    gap: 8px;
  }
  .v9 .v9-browse-pill-label { font-size: 15px !important; }
  .v9 .v9-browse-pill-main { padding: 8px 4px 8px 10px !important; gap: 8px !important; }
  .v9 .v9-browse-pill-badge-word { display: none; }
  .v9 .v9-browse-pill-chev { padding: 0 10px !important; }
}
@media (max-width: 640px) {
  /* Stack search: input + go on row 1; category + location on row 2. */
  .v9 .v9-search { flex-wrap: wrap; }
  .v9 .v9-search-input { order: 1; flex: 1 1 0 !important; width: 0; box-sizing: border-box; min-width: 0 !important; padding: 14px 16px !important; font-size: 16px !important; }
  .v9 .v9-search-go { order: 2; flex: 0 0 52px !important; box-sizing: border-box; padding: 0 !important; font-size: 18px !important; }
  /* Row 2 starts after the field + button (#1030). */
  .v9 .v9-search::after { content: ''; order: 2; flex-basis: 100%; height: 0; }
  .v9 .v9-search-cat { order: 3; box-sizing: border-box; flex: 1 1 50% !important; min-width: 0 !important; max-width: 50%; border-right: 1px solid #e7e5e4 !important; border-bottom: 1px solid #e7e5e4 !important; padding: 10px 12px !important; font-size: 13px !important; overflow: hidden; text-overflow: ellipsis; }
  .v9 .v9-search-level { order: 4; box-sizing: border-box; flex: 1 1 50% !important; min-width: 0 !important; max-width: 50%; border-left: none !important; border-bottom: 1px solid #e7e5e4 !important; padding: 10px 12px !important; font-size: 13px !important; overflow: hidden; text-overflow: ellipsis; }
}
`

// Per-lens editorial styling, keyed by the API's lens id. Labels/descriptions
// are UI copy; the cards & counts under them are real.
const SIGNAL_META: Record<
  string,
  { name: string; icon: string; color: string; bg: string; desc: string }
> = {
  contested: { name: 'Contested', icon: '🔥', color: '#c2410c', bg: '#fff7ed', desc: 'Split votes and heated debate among officials or residents' },
  money: { name: 'Money Moves', icon: '💵', color: '#047857', bg: '#ecfdf5', desc: 'Contracts, grants, and budget changes pulled from the record' },
  flags: { name: 'Raised Eyebrows', icon: '🤨', color: '#7c3aed', bg: '#f5f3ff', desc: 'Unusual patterns — sole-source contracts, reversals, late additions. Manual human review recommended.' },
  soon: { name: 'Moving Fast', icon: '⚡', color: '#b45309', bg: '#fffbeb', desc: 'Items moving quicker than the usual process' },
  next: { name: 'Watch Next', icon: '👀', color: '#1d4ed8', bg: '#eff6ff', desc: 'Upcoming votes worth keeping on your radar' },
}
const WHEN: { label: string; window: string }[] = [
  { label: 'Past month', window: 'month' },
  { label: 'Past 3 months', window: 'quarter' },
  { label: 'Past year', window: 'year' },
  { label: 'All time', window: 'all' },
]

// Map a real /api/meetings card into the shared LensCarousel card shape so the
// "What's New" rail renders the most recent meetings in the same tiles the topic
// lenses use — regardless of whether the meeting produced a decision. Stat chips
// are shown only when there's a genuine count (no fabricated/zero filler).
//
// A meeting that is transcribed but not analyzed yet (analyzed === false, #509)
// says so ("Not yet analyzed"), shows no decision/topic counts (none exist yet),
// links to its recording (there is no meeting page), and — when its transcript
// matched a curated topic or question — quotes that verbatim <mark>ed passage.
const NOT_ANALYZED = 'Not yet analyzed'

function meetingHref(m: MeetingCard): string | undefined {
  if (m.analyzed !== false && m.meeting_id != null) return `/meetings/${m.meeting_id}`
  return m.jump_url || m.video_url || (m.video_id ? `https://www.youtube.com/watch?v=${m.video_id}` : undefined)
}

function meetingToCard(m: MeetingCard): ApiCard {
  const analyzed = m.analyzed !== false
  const stats: ApiCard['stats'] = []
  if (analyzed && m.decision_count > 0)
    stats.push({ value: String(m.decision_count), label: m.decision_count === 1 ? 'Decision' : 'Decisions' })
  if (analyzed && m.question_count > 0)
    stats.push({ value: String(m.question_count), label: m.question_count === 1 ? 'Topic' : 'Topics' })
  return {
    headline: m.title || 'Untitled meeting',
    stats,
    jurisdiction: m.city || m.jurisdiction || '',
    date: m.date || undefined,
    url: meetingHref(m),
    state_code: m.state_code || undefined,
    state: m.state || undefined,
    video_id: m.video_id,
    description: analyzed ? undefined : m.evidence || undefined,
    description_label: analyzed ? undefined : m.evidence_label || undefined,
    status: analyzed ? undefined : NOT_ANALYZED,
  }
}

// Left-side search scope: the shared category list (lib/searchCategories, #1221).
// `types` is handed to /search as ?types= and an organization sub-type row adds
// ?org_type=; 'All' sends no types param so the search spans everything.

// ---- /api/lenses response (the subset we render) ----
interface LensActivity {
  icon: string
  value: string
  label: string
  query?: string
}
interface LensCard {
  headline: string
  jurisdiction: string
  date?: string
  url?: string
  // The same /api/lenses cards also carry per-card stat chips ("5–4 Vote",
  // "1 Opposing views") and a state code — rendered by the LensCarousel.
  stats: { value: string; label: string; tone?: 'plain' | 'green' | 'amber' | 'red' | 'blue' | 'purple' }[]
  badge?: string
  state_code?: string
  state?: string
}
interface LensBlock {
  id: string
  label: string
  placeholder: boolean
  cards: LensCard[]
}
interface LensesResp {
  lenses: LensBlock[]
  activity: LensActivity[]
  /** The window the cards cover: the requested one, or what `auto` resolved to (#1045). */
  window?: string
  location_label?: string
}

// One row of the hero search typeahead — a real /api/search result.
interface SearchSuggestion {
  type: string
  title: string
  subtitle?: string | null
  url: string
  score?: number
}

// One row from GET /api/browse/summary (categories[], pre-sorted by
// transcript_count desc with `place` always last — far right). transcript_count is a real
// distinct-transcript count; has_transcripts is false only for cause (no
// transcript linkage exists in the data).
interface BrowseSummaryCategory {
  entity_type: string
  label: string
  transcript_count: number
  entity_count: number
  has_transcripts: boolean
}

// Per-category lookup the browse cards read: the real transcript count, whether
// any transcripts are linked, and the API's ordering index (for card sort).
interface DirectorySummaryEntry {
  transcript_count: number
  has_transcripts: boolean
  order: number
}

interface DirectorySummary {
  byType: Record<string, DirectorySummaryEntry>
}

// One row from GET /api/browse/top-items — a single browseable item with its
// genuine distinct-transcript count. Drives the flyout previews so every
// dropdown row (including causes) shows a real transcript count.
interface BrowseTopItem {
  entity_id: string
  entity_name: string
  transcript_count: number
  // Nullable, as the API's BrowseTopItem: question/cause items have none; place/topic carry one.
  state_code?: string | null
}

// Maps each browse card's stable `key` to the API's entity_type so cards can
// pull their real count + ordering from the /browse/summary lookup.
const BROWSE_CARD_ENTITY_TYPE: Record<'questions' | 'topics' | 'causes' | 'places', string> = {
  questions: 'question',
  topics: 'topic',
  causes: 'cause',
  places: 'place',
}

// Emoji marker per result type for the typeahead rows (visual scent only).
const SUGGEST_ICON: Record<string, string> = {
  topic: '🏷️',
  organization: '🏢',
  person: '👤',
  leader: '🎖️',
  decision: '⚖️',
  bill: '📜',
  cause: '💚',
  question: '⚖️',
  meeting: '🗓️',
}

// ── Small pieces ──────────────────────────────────────────────────────────
function Chip({
  active,
  children,
  onClick,
  style,
}: {
  active?: boolean
  children: React.ReactNode
  onClick?: () => void
  style?: React.CSSProperties
}) {
  return (
    <button
      onClick={onClick}
      className="font-body"
      style={{
        padding: '8px 16px',
        borderRadius: 999,
        border: `1px solid ${active ? TEAL : '#d6d3d1'}`,
        background: active ? TEAL : '#fff',
        color: active ? '#fff' : '#1c1917',
        boxShadow: active ? 'none' : '0 1px 2px rgba(28,25,23,0.05)',
        fontSize: 14.5,
        fontWeight: 600,
        cursor: 'pointer',
        whiteSpace: 'nowrap',
        transition: 'all 120ms ease',
        ...style,
      }}
    >
      {children}
    </button>
  )
}

// ── Money hook (compact banner; opens the REAL modal) ───────────────────────
// The "How much of your money is on the line?" teal banner. The CTA simply opens
// the real <MoneyGameModal>; the modal itself owns location — if we already know
// the user's place it loads the bill, otherwise tab 1 shows the "where's home?"
// ZIP gate. No location is ever fabricated.
function MoneyHookBanner() {
  const { location } = useLocationContext()
  const [modalOpen, setModalOpen] = useState(false)

  return (
    <section style={{ paddingTop: 22 }}>
      {/* Compact teal banner — the screenshot's "money on the line" hook. */}
      <div
        className="v9-money-hook"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          flexWrap: 'wrap',
          background: '#ecfdf5',
          border: '1px solid #99f6e4',
          borderRadius: 16,
          padding: '16px 22px',
        }}
      >
        <span style={{ fontSize: 30, lineHeight: 1, flexShrink: 0 }}>💵</span>
        <div className="v9-money-hook-text" style={{ flex: 1, minWidth: 0 }}>
          <div className="font-display" style={{ fontSize: 'clamp(19px, 2.4vw, 23px)', fontWeight: 800, lineHeight: 1.15, color: INK }}>
            How much of <span style={{ color: TEAL }}>your money</span> is on the line?
          </div>
          <div style={{ fontSize: 14, color: '#57534e', marginTop: 4 }}>
            See what you pay in local taxes, where it goes, and what it means for your grandkids. About 90 seconds.
          </div>
        </div>
        <button
          type="button"
          className="v9-money-hook-cta"
          onClick={() => setModalOpen(true)}
          style={{ background: TEAL, color: '#fff', border: 'none', borderRadius: 999, padding: '12px 24px', fontSize: 15, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', whiteSpace: 'nowrap', flexShrink: 0 }}
        >
          Show me my money →
        </button>
      </div>

      <MoneyGameModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        stateCode={location?.state}
        city={location?.city || undefined}
        county={location?.county || undefined}
        requestedLabel={location?.city || location?.county || location?.state || undefined}
      />
    </section>
  )
}

// ── Step 0: Why should I care? (Personal Impact Assessment) ─────────────────
// The "before you do anything, here's why it matters to YOU" framing that opens
// the How-it-works section. Both CTAs open the REAL <MoneyGameModal>: the cost
// estimator lands on the bill stage, the income-trends button jumps straight to
// the Opportunity Atlas (grandkids) mobility view. No figures are shown here —
// every number lives behind the modal, sourced from the warehouse.
function StepZeroImpact() {
  const { location } = useLocationContext()
  const [modal, setModal] = useState<null | 'estimate' | 'grandkids'>(null)

  // Human label for the intro line, derived from the saved place — never faked.
  const placeLabel =
    location?.city && location?.county
      ? `${location.city} and ${location.county}`
      : location?.city || location?.county || location?.state || 'your community'

  return (
    <div
      style={{
        background: '#f0fdfa',
        border: '1px solid #99f6e4',
        borderRadius: 18,
        padding: 'clamp(16px, 2.2vw, 22px)',
        marginBottom: 22,
        maxWidth: 760,
        marginLeft: 'auto',
        marginRight: 'auto',
        textAlign: 'center',
      }}
    >
      <div className="font-display" style={{ fontSize: 'clamp(18px, 2.3vw, 21px)', fontWeight: 800, color: INK }}>
        Step 0 · Why should I care? <span style={{ color: TEAL_DARK }}>Personal Impact</span>
      </div>
      <p style={{ fontSize: 14, color: '#44403c', lineHeight: 1.45, margin: '6px auto 0', maxWidth: 560 }}>
        Local decisions shape your taxes, schools, safety, and your family&apos;s future — whether you engage or not.
        Doing nothing is a choice too, with real consequences for you and your children.
      </p>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap', marginTop: 14 }}>
        <button
          onClick={() => setModal('estimate')}
          style={{ background: TEAL, color: '#fff', border: 'none', borderRadius: 999, padding: '11px 22px', fontSize: 14.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
        >
          💵 Try the cost estimator
        </button>
        <button
          onClick={() => setModal('grandkids')}
          style={{ background: '#fff', color: TEAL_DARK, border: '1px solid #99f6e4', borderRadius: 999, padding: '11px 22px', fontSize: 14.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
        >
          📈 View income mobility trends
        </button>
      </div>

      <MoneyGameModal
        open={modal !== null}
        onClose={() => setModal(null)}
        stateCode={location?.state}
        city={location?.city || undefined}
        county={location?.county || undefined}
        requestedLabel={location?.city || location?.county || location?.state || undefined}
        initialStage={modal === 'grandkids' ? 'grandkids' : 'estimate'}
      />

      <p style={{ fontSize: 12.5, color: '#57534e', marginTop: 10 }}>
        Scoped to {placeLabel} once you confirm where home is.
      </p>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function HomeV9() {
  // Phones get a shorter search placeholder that fits beside the button (#1030).
  const narrow = useMediaQuery('(max-width: 760px)')
  const navigate = useNavigate()
  const { location } = useLocationContext()
  // A place carried in the address (?state=&city=, e.g. from a header tab on a scoped page) sets the whole page's
  // scope, ahead of the saved location, without overwriting it (#975; CLAUDE.md: filters carry over via the URL).
  const [urlParams] = useSearchParams()
  const urlState = (urlParams.get('state') ?? '').trim().toUpperCase()
  const urlHasPlace = STATE_CODES.includes(urlState)
  const locState = urlHasPlace ? urlState : location?.state || undefined
  const locCity = urlHasPlace ? (urlParams.get('city') ?? '').trim() || undefined : location?.city || undefined

  // ── Location level — City / State / National ──
  // Restores the geography selector that used to live in the hero. Defaults to
  // the most specific level the saved location supports, and resets to that
  // default whenever the saved location changes — unless the user has manually
  // picked a level (via the dropdown or the "expand" prompt below).
  type Level = 'city' | 'state' | 'national'
  const naturalLevel = (): Level => (locCity ? 'city' : locState ? 'state' : 'national')
  const [level, setLevel] = useState<Level>(naturalLevel)
  const levelPicked = useRef(false)
  const [levelOpen, setLevelOpen] = useState(false)
  // Inline "change location" picker inside the level menu (restores the ability
  // to switch to a different city/place, not just City/State/National scope).
  const [changingLoc, setChangingLoc] = useState(false)
  const levelRef = useRef<HTMLButtonElement>(null)
  const closePicker = useCallback(() => setChangingLoc(false), [])
  // A pick (here or in the header) saves the place and clears any carried ?state=&city= (usePlacePick); the scope then
  // falls back to the new place's natural level.
  const pickPlace = usePlacePick()
  // A pick re-derives the level for the new place even when the reader had picked one (pickTick re-runs the effect below
  // after the reset, whichever order the pick's renders land in).
  const [pickTick, setPickTick] = useState(0)
  useEffect(() => {
    const onPicked = () => {
      levelPicked.current = false
      setPickTick((t) => t + 1)
    }
    window.addEventListener(PLACE_PICKED_EVENT, onPicked)
    return () => window.removeEventListener(PLACE_PICKED_EVENT, onPicked)
  }, [])
  useDocumentTitle(null)
  const levelMenuRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (levelPicked.current) return
    setLevel(locCity ? 'city' : locState ? 'state' : 'national')
  }, [locCity, locState, pickTick])
  useEffect(() => {
    if (!levelOpen) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node
      if (levelRef.current?.contains(t) || levelMenuRef.current?.contains(t)) return
      setLevelOpen(false)
      setChangingLoc(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [levelOpen])
  const pickLevel = (v: Level) => {
    levelPicked.current = true
    setLevel(v)
    setLevelOpen(false)
  }
  // The story title's place control (#1206): The United States sets the level to National (the saved place is kept, as
  // the level menu's National does); a state or city goes through the header's pick path, so the saved location, the
  // header label and the level (City / State, from the new place) move together.
  const applyTitlePlace = (code: string | null, pickedCity: string | null) => {
    if (!code) {
      pickLevel('national')
      return
    }
    pickPlace(
      pickedCity
        ? { state: code, city: pickedCity, county: '' }
        : { state: code, city: '', county: '', granularity: 'state' },
    )
  }

  // The active scope flows from `level` into every place-scoped query below.
  const national = level === 'national' || !locState
  const stateCode = national ? undefined : locState
  const city = level === 'city' ? locCity : undefined
  // URL params for the ACTIVE scope (the one the scope label names), never the
  // saved location: with National selected, links carry no place at all (#350).
  const activeScopeParams = (): URLSearchParams => {
    const p = new URLSearchParams()
    if (stateCode) p.set('state', stateCode)
    if (stateCode && city) p.set('city', city)
    return p
  }
  const placeLabel =
    level === 'national' || !locState
      ? 'the U.S.'
      : level === 'state'
        ? locState
        : locCity || location?.county || locState

  const levelOptions: { value: Level; label: string; disabled: boolean }[] = [
    { value: 'city', label: locCity ? `City · ${locCity}` : 'City', disabled: !locCity },
    { value: 'state', label: locState ? `State · ${locState}` : 'State', disabled: !locState },
    { value: 'national', label: 'National · U.S.', disabled: false },
  ]

  const [query, setQuery] = useState('')
  const [searchFocused, setSearchFocused] = useState(false)
  // Left-side category scope for the hero search box.
  const [cat, setCat] = useState<SearchCategory>(SEARCH_CATEGORIES[0])
  const [catOpen, setCatOpen] = useState(false)
  const catRef = useRef<HTMLButtonElement>(null)
  const catMenuRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!catOpen) return
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node
      if (catRef.current?.contains(t) || catMenuRef.current?.contains(t)) return
      setCatOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [catOpen])
  // Live typeahead: a debounced copy of `query` drives the suggestions query so
  // we don't fire a request per keystroke. `suggestOpen` lets a click on a
  // suggestion win the race against the input's blur (cleared on select/enter).
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [suggestOpen, setSuggestOpen] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 220)
    return () => clearTimeout(t)
  }, [query])
  // null until the reader picks a window: the lenses ask for `auto`, the narrowest window that has decisions for the
  // place, and the chip for the window the API resolved to is highlighted (#1045), so an Alabama reader whose newest
  // analysed decision is months old isn't greeted by an empty "Past month".
  const [pickedWhen, setWhen] = useState<(typeof WHEN)[number] | null>(null)
  const [showStrategicPlan, setShowStrategicPlan] = useState(false)

  // When arriving from another page via `/#how-it-works` (shared header nav),
  // scroll to the requested in-page section once it has rendered.
  // The sections above load their data after this runs and grow, which would leave the section mid-screen (#975), so
  // the scroll settles again a few times while the page fills in, and stops as soon as the reader scrolls, clicks,
  // presses a key or navigates.
  useEffect(() => {
    const id = window.location.hash.replace('#', '')
    if (!id) return
    let userMoved = false
    const stop = () => {
      userMoved = true
    }
    const opts = { passive: true } as const
    window.addEventListener('wheel', stop, opts)
    window.addEventListener('touchstart', stop, opts)
    window.addEventListener('pointerdown', stop, opts)
    window.addEventListener('keydown', stop)
    window.addEventListener('hashchange', stop)
    window.addEventListener('popstate', stop)
    const settle = () => {
      if (userMoved) return
      const el = document.getElementById(id)
      if (el && Math.abs(el.getBoundingClientRect().top - 72) > 8) el.scrollIntoView({ behavior: 'auto', block: 'start' })
    }
    const raf = requestAnimationFrame(settle)
    const timers = [300, 800, 1500, 2500, 4000].map((ms) => window.setTimeout(settle, ms))
    return () => {
      cancelAnimationFrame(raf)
      timers.forEach((t) => window.clearTimeout(t))
      window.removeEventListener('wheel', stop)
      window.removeEventListener('touchstart', stop)
      window.removeEventListener('pointerdown', stop)
      window.removeEventListener('keydown', stop)
      window.removeEventListener('hashchange', stop)
      window.removeEventListener('popstate', stop)
    }
  }, [])

  // Logo click (SiteHeader) resets the hero when already on the home route.
  useEffect(() => {
    const onGoHome = () => {
      setQuery('')
      setDebouncedQuery('')
      setSuggestOpen(false)
      setSearchFocused(false)
      setCatOpen(false)
      setLevelOpen(false)
      setChangingLoc(false)
    }
    window.addEventListener('open-navigator:go-home', onGoHome)
    return () => window.removeEventListener('open-navigator:go-home', onGoHome)
  }, [])

  // ── Real data ──
  const { data: lensesData } = useQuery<LensesResp>({
    queryKey: ['home-v9-lenses', national, stateCode, city, pickedWhen?.window ?? 'auto'],
    queryFn: () => {
      const params: Record<string, string> = { window: pickedWhen?.window ?? 'auto' }
      if (!national && stateCode) params.state = stateCode
      if (!national && city) params.city = city
      return api.get('/lenses', { params }).then((r) => r.data)
    },
    staleTime: 5 * 60 * 1000,
  })
  // The window the shown cards cover: the reader's pick, else what `auto` resolved to.
  const when: { label: string; window: string } = pickedWhen ??
    WHEN.find((w) => w.window === lensesData?.window) ??
    (lensesData?.window === 'fiveyear'
      ? { label: 'Past 5 years', window: 'fiveyear' }
      : { label: 'Recent', window: lensesData?.window ?? 'auto' })

  // ── Recent meetings (REAL /api/meetings, sort=recent) ──
  // Fallback content for the Contested / Raised Eyebrows lenses: when this place
  // has analyzed transcripts but no lens activity yet (no contested votes or
  // flagged patterns surfaced), we'd otherwise show two empty "No activity"
  // cards. Instead we show the most recent meetings here — a real, useful
  // signal — and hide the empty lens sections. Always a small page; only
  // actually rendered when both lenses come back empty.
  const { data: recentMeetingsData } = useQuery<MeetingCard[]>({
    queryKey: ['home-v9-recent-meetings', national, stateCode, city],
    queryFn: () =>
      fetchMeetings({
        state: national ? undefined : stateCode || undefined,
        city: national ? undefined : city || undefined,
        sort: 'recent',
        limit: 6,
      }).then((r) => r.items),
    staleTime: 5 * 60 * 1000,
  })
  const recentMeetings = recentMeetingsData ?? []

  // Browse-card badges are a genuine distinct-transcript count per category,
  // served pre-sorted (transcript_count desc, place pinned far right) by /api/browse/summary.
  // We index by entity_type so each card can read its real count + ordering and
  // honor has_transcripts (cause has no transcript linkage → honest em-dash).
  const { data: directoryCounts } = useQuery<DirectorySummary>({
    queryKey: ['home-v9-directory-counts', stateCode, national],
    queryFn: async () => {
      const params: Record<string, string> = {}
      if (!national && stateCode) params.state = stateCode
      const res = await api
        .get('/browse/summary', { params })
        .then((r) => r.data as { categories?: BrowseSummaryCategory[] })
        .catch(() => null)
      const categories = res?.categories ?? []
      const byType: Record<string, DirectorySummaryEntry> = {}
      categories.forEach((c, index) => {
        byType[c.entity_type] = {
          transcript_count: c.transcript_count,
          has_transcripts: c.has_transcripts,
          order: index,
        }
      })
      return { byType }
    },
    staleTime: 5 * 60 * 1000,
  })

  // ── Browse-pill flyout state + top-item previews (REAL data only) ──
  // Exactly one flyout open at a time. On touch devices the pill toggles on
  // click; on hover-capable devices it opens on mouseenter.
  const [browseOpen, setBrowseOpen] = useState<'topics' | 'causes' | 'questions' | 'places' | null>(null)
  const [isTouch] = useState(
    () => typeof window !== 'undefined' && !!window.matchMedia?.('(hover: none)').matches,
  )

  // Flyout previews: the top ~5 items per browse category, each carrying its
  // REAL distinct-transcript count, from the canonical /api/browse/top-items
  // endpoint (ordered transcript_count desc). Sourcing all four categories —
  // including causes — from this one endpoint guarantees every dropdown row
  // shows a genuine transcript count. Causes are honestly 0: no cause↔transcript
  // linkage exists in the warehouse, so that 0 is real, not fabricated.
  // State-scoped (place/topic) when a state is selected.
  const { data: browseTopItems } = useQuery<Record<string, BrowseTopItem[]>>({
    queryKey: ['home-v9-browse-top-items', stateCode, national],
    queryFn: async () => {
      const fetchType = async (entityType: string): Promise<BrowseTopItem[]> => {
        const params: Record<string, string | number> = { entity_type: entityType, limit: 5 }
        if (!national && stateCode) params.state = stateCode
        const res = await api
          .get('/browse/top-items', { params })
          .then((r) => r.data as { items?: BrowseTopItem[] })
          .catch(() => null)
        return res?.items ?? []
      }
      const [topic, question, place, cause] = await Promise.all([
        fetchType('topic'),
        fetchType('question'),
        fetchType('place'),
        fetchType('cause'),
      ])
      return { topic, question, place, cause }
    },
    staleTime: 30 * 60 * 1000,
  })

  // ── "Search in" category counts (real /api/search type_totals) ──
  // Per-category match counts for the category dropdown, DYNAMIC on the search
  // text: re-runs as the (debounced) query / place changes so each row shows how
  // many real results that scope would return. Fetched lazily (only while the
  // menu is open) with limit=1 — we want `type_totals`, not rows — so it never
  // slows the hero. No fabricated numbers: a type the API doesn't count is blank.
  // Organization sub-type counts (#1221) in their OWN organizations-only call, so
  // the sub-rows get real numbers (and the exact org total) without waiting on
  // the slow transcript legs of the all-types call below. The API omits
  // org_type_totals on timeout, and those rows then show no badge.
  const { data: orgFacetData, isFetching: orgFacetFetching } = useQuery<{
    total?: number
    byType?: Record<string, number>
  }>({
    queryKey: ['home-v9-org-facets', debouncedQuery, national, stateCode, city],
    queryFn: async () => {
      const params: Record<string, string> = { types: 'organizations', facets: 'org_type', limit: '1' }
      if (debouncedQuery.length >= 2) params.q = debouncedQuery
      if (!national && stateCode) params.state = stateCode
      if (!national && city) params.city = city
      const res = await api.get('/search/', { params }).then((r) => r.data).catch(() => null)
      if (!res?.org_type_totals) return {}
      return { total: res.organizations_total, byType: res.org_type_totals as Record<string, number> }
    },
    enabled: catOpen,
    staleTime: 60 * 1000,
    placeholderData: (prev) => prev,
  })
  const orgFacetSettled = !orgFacetFetching
  const { data: catCountsData, isFetching: catCountsFetching } = useQuery<Record<string, number>>({
    queryKey: ['home-v9-cat-counts', debouncedQuery, national, stateCode, city],
    queryFn: async () => {
      const params: Record<string, string> = {
        types: SEARCH_CATEGORY_TYPES.join(','),
        limit: '1',
      }
      if (debouncedQuery.length >= 2) params.q = debouncedQuery
      if (!national && stateCode) params.state = stateCode
      if (!national && city) params.city = city
      const res = await api.get('/search/', { params }).then((r) => r.data).catch(() => null)
      return (res?.type_totals ?? {}) as Record<string, number>
    },
    // Starts once the cheap org facet call below has settled, so the two don't
    // contend for the DB at the same moment (the all-types call is the heavy one).
    enabled: catOpen && orgFacetSettled,
    staleTime: 60 * 1000,
    placeholderData: (prev) => prev, // keep last counts while the next query loads
  })
  // Each row maps 1:1 to its type_totals key (c.types); undefined when the API
  // didn't count that type (→ no badge). 'All' intentionally shows NO count: its
  // only honest value would be the sum across every type, but those catalogs sit
  // at different geographic grains (local meetings/decisions vs. state bills,
  // grants, and national questions/topics), so a single total reads as nonsense
  // next to the local rows. The per-category numbers are the coherent signal.
  const countForCat = (c: SearchCategory): number | undefined =>
    countForCategory(
      c,
      // The facet call's exact org total wins over the all-types estimate.
      orgFacetData?.total != null ? { ...catCountsData, organizations: orgFacetData.total } : catCountsData,
      orgFacetData?.byType,
    )

  // ── Search typeahead (real /api/search results) ──
  // Queries only the FAST search types — `documents` (transcript full-text) runs
  // a ~2-3s COUNT and is deliberately excluded so per-keystroke suggestions stay
  // snappy. Results are scoped to the active place. No fabricated rows: an empty
  // response renders nothing.
  const { data: suggestData, isFetching: suggestFetching } = useQuery<SearchSuggestion[]>({
    queryKey: ['home-v9-suggest', debouncedQuery, stateCode, city],
    queryFn: async () => {
      const params: Record<string, string> = {
        q: debouncedQuery,
        limit: '4',
        types: 'topics,organizations,people,leaders,decisions,bills,causes,questions',
      }
      if (!national && stateCode) params.state = stateCode
      if (!national && city) params.city = city
      const res = await api.get('/search/', { params }).then((r) => r.data)
      const groups = (res?.results ?? {}) as Record<string, SearchSuggestion[]>
      return Object.values(groups)
        .flat()
        .filter((r) => r && r.title && r.url)
        .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
        .slice(0, 7)
    },
    enabled: debouncedQuery.length >= 2,
    staleTime: 60 * 1000,
    placeholderData: (prev) => prev,
  })
  const suggestions = suggestData ?? []
  const showSuggest = suggestOpen && query.trim().length >= 2

  // ── Derived (all real) ──
  const lenses = lensesData?.lenses ?? []
  const lensById = useMemo(() => {
    const m: Record<string, LensBlock> = {}
    for (const l of lenses) m[l.id] = l
    return m
  }, [lenses])

  const runSearch = (q?: string) => {
    const term = (q ?? query).trim()
    setSuggestOpen(false)
    const params = new URLSearchParams()
    if (term) params.set('q', term)
    if (cat.types) params.set('types', cat.types)
    if (cat.orgType) params.set('org_type', cat.orgType)
    if (!national && stateCode) params.set('state', stateCode)
    // Carry the city through so a drill-down from e.g. Tuscaloosa reads
    // "City: Tuscaloosa" rather than just "State: AL" (UnifiedSearch reads ?city=).
    if (!national && city) params.set('city', city)
    navigate(`/search?${params.toString()}`, { state: { fromHome: true } })
  }

  // Jump straight to a suggested entity's real detail/search URL.
  const selectSuggestion = (s: SearchSuggestion) => {
    setSuggestOpen(false)
    setQuery(s.title)
    navigate(s.url, { state: { fromHome: true } })
  }

  return (
    <div className="v9 font-body" style={{ background: '#fafaf9', minHeight: '100vh', color: INK }}>
      <style>{FONTS}</style>

      {/* ── Shared header (identical to the search page) ── */}
      <SiteHeader />

      {/* ── Data stories first (#995): the conclusion, the quote map and the topics; the header's Data Stories tab. ── */}
      <main id="main-content" tabIndex={-1} style={{ outline: 'none' }}>
      <HomeDataStories stateCode={stateCode} city={city ?? null} onPlaceApply={applyTitlePlace} />

      <div className="v9-main" style={{ maxWidth: 1180, margin: '0 auto', padding: '0 24px' }}>
        {/* ── Hero: thesis + search + trending ── */}
        {/* The header's Search tab scrolls here (#975); results open on /search from this search. */}
        <section id="search" className="v9-hero" style={{ padding: '44px 0 6px', textAlign: 'center', scrollMarginTop: 72 }}>
          {/* #995: the thesis ("Every local decision, in one place.") now closes the page, under Impact. */}
          <h2 className="font-display" style={{ fontSize: 'clamp(28px, 4vw, 40px)', fontWeight: 800, margin: 0, lineHeight: 1.1, color: INK }}>
            Search your community
          </h2>

          {/* ── Find your town (#1179): opens the location picker. No place list is hard-coded; any town the
              geocoder finds can be picked, and pages show an honest empty state where we have no meetings. ── */}
          <button
            type="button"
            className="v9-find-town"
            onClick={() => setChangingLoc(true)}
            aria-haspopup="dialog"
          >
            <span aria-hidden="true">📍</span>
            {locState ? (
              <span>
                <strong>{[locCity, locState].filter(Boolean).join(', ')}</strong> · Find another town
              </span>
            ) : (
              <span>
                <strong>Find your town</strong> · see what its meetings said and decided
              </span>
            )}
            <span aria-hidden="true">→</span>
          </button>

          <div style={{ position: 'relative', maxWidth: 760, margin: '28px auto 0', textAlign: 'left' }}>
            <div
              className="v9-search"
              style={{
                background: '#fff',
                border: `2px solid ${TEAL}`,
                borderRadius: showSuggest ? '16px 16px 0 0' : 16,
                boxShadow: searchFocused
                  ? `0 0 0 4px rgba(13,148,136,0.18), 0 14px 36px rgba(13,148,136,0.22)`
                  : `0 10px 30px rgba(13,148,136,0.15)`,
                transition: 'box-shadow .2s ease',
                overflow: 'hidden',
              }}
            >
              {/* Left-side category scope — pick Decisions, Bills, Leaders, etc. */}
              <button
                ref={catRef}
                type="button"
                className="v9-search-cat"
                onClick={() => setCatOpen((o) => !o)}
                aria-haspopup="listbox"
                aria-expanded={catOpen}
                aria-label={`${cat.label}, search category`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  flexShrink: 0,
                  background: 'none',
                  border: 'none',
                  borderRight: '1px solid #e7e5e4',
                  padding: '0 16px',
                  fontSize: 15,
                  fontWeight: 600,
                  color: INK,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  whiteSpace: 'nowrap',
                }}
              >
                {cat.label}
                <span
                  style={{
                    fontSize: 11,
                    color: '#78716c',
                    transform: catOpen ? 'rotate(180deg)' : 'none',
                    transition: 'transform .15s ease',
                  }}
                  aria-hidden
                >
                  ▾
                </span>
              </button>

              <input
                className="v9-search-input"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setSuggestOpen(true)
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') runSearch()
                  else if (e.key === 'Escape') setSuggestOpen(false)
                }}
                onFocus={() => {
                  setSearchFocused(true)
                  setSuggestOpen(true)
                }}
                // Delay the close so a mousedown on a suggestion row still fires
                // its onClick before the dropdown unmounts.
                onBlur={() => {
                  setSearchFocused(false)
                  setTimeout(() => setSuggestOpen(false), 140)
                }}
                placeholder={narrow ? 'Search topics, people, causes…' : 'Search topics, people, organizations, or causes'}
                style={{ flex: 1, border: 'none', outline: 'none', padding: '18px 20px', fontSize: 17, fontFamily: 'inherit', minWidth: 0 }}
              />
              <button
                ref={levelRef}
                type="button"
                className="v9-search-level"
                onClick={() => setLevelOpen((o) => !o)}
                aria-haspopup="listbox"
                aria-expanded={levelOpen}
                aria-label={`${placeLabel}, location level`}
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0 14px', borderLeft: '1px solid #e7e5e4', background: 'none', color: '#44403c', fontSize: 14.5, fontWeight: 600, whiteSpace: 'nowrap', cursor: 'pointer', fontFamily: 'inherit', minWidth: 0 }}
              >
                📍 {placeLabel}
                <span
                  style={{ fontSize: 11, color: '#78716c', transform: levelOpen ? 'rotate(180deg)' : 'none', transition: 'transform .15s ease' }}
                  aria-hidden
                >
                  ▾
                </span>
              </button>
              <button
                className="v9-search-go"
                aria-label="Search"
                onClick={() => runSearch()}
                style={{ background: TEAL, color: '#fff', border: 'none', padding: '0 28px', fontSize: 20, cursor: 'pointer', flexShrink: 0 }}
                onMouseEnter={(e) => (e.currentTarget.style.background = TEAL_DARK)}
                onMouseLeave={(e) => (e.currentTarget.style.background = TEAL)}
              >
                🔍
              </button>
            </div>

            {/* Category scope menu — anchored to the outer relative wrapper so it
                escapes the search box's overflow:hidden clipping. */}
            {catOpen && (
              <div
                ref={catMenuRef}
                role="listbox"
                aria-label="Search category"
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 8px)',
                  left: 0,
                  zIndex: 50,
                  minWidth: 220,
                  background: '#fff',
                  border: '1px solid #e7e5e4',
                  borderRadius: 14,
                  boxShadow: '0 16px 38px rgba(13,148,136,0.20)',
                  padding: 6,
                  maxHeight: 380,
                  overflowY: 'auto',
                }}
              >
                <div
                  style={{
                    padding: '6px 10px 8px',
                    fontSize: 11,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: '#78716c',
                  }}
                >
                  Search in
                </div>
                {SEARCH_CATEGORIES.map((c) => {
                  const selected = c.id === cat.id
                  const n = countForCat(c)
                  // While the (lazy, ~2s) count query is in flight and we don't yet
                  // have a number for this row, show a skeleton instead of a blank
                  // so the counts read as "loading", not "missing". 'All' never
                  // shows a count, so it never shows a skeleton.
                  const showCountSkeleton =
                    c.id !== 'all' && n == null && (c.types === 'organizations' ? orgFacetFetching : catCountsFetching || !orgFacetSettled)
                  return (
                    <button
                      key={c.id}
                      type="button"
                      role="option"
                      aria-selected={selected}
                      // Sub-type rows are only indented visually; name the parent for screen readers.
                      aria-label={c.child ? `Organizations: ${c.label}${n != null ? `, ${n.toLocaleString('en-US')}` : ''}` : undefined}
                      onClick={() => {
                        setCat(c)
                        setCatOpen(false)
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        width: '100%',
                        textAlign: 'left',
                        background: selected ? '#f0fdfa' : 'none',
                        border: 'none',
                        borderRadius: 9,
                        padding: c.child ? '7px 12px 7px 28px' : '9px 12px',
                        fontSize: c.child ? 13.5 : 14.5,
                        fontWeight: selected ? 700 : 500,
                        color: selected ? TEAL_DARK : '#44403c',
                        cursor: 'pointer',
                        fontFamily: 'inherit',
                      }}
                      onMouseEnter={(e) => {
                        if (!selected) e.currentTarget.style.background = '#f5f5f4'
                      }}
                      onMouseLeave={(e) => {
                        if (!selected) e.currentTarget.style.background = 'none'
                      }}
                    >
                      <span>{c.label}</span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {n != null ? (
                          <span
                            className="font-mono-x"
                            style={{ fontSize: 11.5, fontWeight: 600, color: selected ? TEAL_DARK : '#78716c', fontVariantNumeric: 'tabular-nums' }}
                          >
                            {n.toLocaleString('en-US')}
                          </span>
                        ) : showCountSkeleton ? (
                          <span
                            aria-hidden
                            className="animate-pulse"
                            style={{ width: 22, height: 9, borderRadius: 4, background: '#e7e5e4' }}
                          />
                        ) : null}
                        {selected && <span style={{ color: TEAL }} aria-hidden>✓</span>}
                      </span>
                    </button>
                  )
                })}
              </div>
            )}

            {/* Location-level menu — City / State / National. Anchored to the
                outer relative wrapper so it escapes the search box clipping. */}
            {levelOpen && (
              <div
                ref={levelMenuRef}
                role="listbox"
                aria-label="Location level"
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 8px)',
                  right: 64,
                  zIndex: 50,
                  minWidth: 220,
                  background: '#fff',
                  border: '1px solid #e7e5e4',
                  borderRadius: 14,
                  boxShadow: '0 16px 38px rgba(13,148,136,0.20)',
                  padding: 6,
                }}
              >
                <div
                  style={{ padding: '6px 10px 8px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#78716c' }}
                >
                  Show results for
                </div>
                {levelOptions.map((opt) => {
                  const selected = level === opt.value
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      role="option"
                      aria-selected={selected}
                      disabled={opt.disabled}
                      onClick={() => pickLevel(opt.value)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        width: '100%',
                        textAlign: 'left',
                        background: selected ? '#f0fdfa' : 'none',
                        border: 'none',
                        borderRadius: 9,
                        padding: '9px 12px',
                        fontSize: 14.5,
                        fontWeight: selected ? 700 : 500,
                        color: opt.disabled ? '#d6d3d1' : selected ? TEAL_DARK : '#44403c',
                        cursor: opt.disabled ? 'not-allowed' : 'pointer',
                        fontFamily: 'inherit',
                      }}
                      onMouseEnter={(e) => {
                        if (!selected && !opt.disabled) e.currentTarget.style.background = '#f5f5f4'
                      }}
                      onMouseLeave={(e) => {
                        if (!selected && !opt.disabled) e.currentTarget.style.background = 'none'
                      }}
                    >
                      <span>{opt.label}</span>
                      {selected && <span style={{ color: TEAL }} aria-hidden>✓</span>}
                    </button>
                  )
                })}
                <div style={{ borderTop: '1px solid #f5f5f4', marginTop: 4, paddingTop: 4 }}>
                  <button
                    type="button"
                    onClick={() => {
                      setLevelOpen(false)
                      setChangingLoc(true)
                    }}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left', background: 'none', border: 'none', borderRadius: 9, padding: '9px 12px', fontSize: 13.5, fontWeight: 600, color: TEAL_DARK, cursor: 'pointer', fontFamily: 'inherit' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#f5f5f4')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                  >
                    📍 {locState ? 'Change location' : 'Set your location'}
                  </button>
                </div>
              </div>
            )}

            {/* Change-location popup: the shared picker (#1191), also opened from the header's place control. */}
            <LocationPickerDialog
              open={changingLoc}
              onClose={closePicker}
              current={locState ? [locCity, locState].filter(Boolean).join(', ') : null}
              onPicked={pickPlace}
            />

            {/* Live typeahead dropdown — real /api/search results, scoped to the
                active place. mouseDown-preventDefault keeps focus so onClick wins
                the blur race. */}
            {showSuggest && (
              <div
                style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  zIndex: 40,
                  background: '#fff',
                  border: `2px solid ${TEAL}`,
                  borderTop: 'none',
                  borderRadius: '0 0 16px 16px',
                  boxShadow: '0 18px 40px rgba(13,148,136,0.18)',
                  overflow: 'hidden',
                }}
                onMouseDown={(e) => e.preventDefault()}
              >
                {suggestions.length > 0 ? (
                  suggestions.map((s, i) => (
                    <button
                      key={`${s.type}-${s.url}-${i}`}
                      onClick={() => selectSuggestion(s)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        width: '100%',
                        textAlign: 'left',
                        background: 'transparent',
                        border: 'none',
                        borderTop: i === 0 ? 'none' : '1px solid #f5f5f4',
                        padding: '11px 18px',
                        cursor: 'pointer',
                        fontFamily: 'inherit',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = '#f0fdfa')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      <span style={{ fontSize: 17, flexShrink: 0 }}>{SUGGEST_ICON[s.type] ?? '🔎'}</span>
                      <span style={{ minWidth: 0, flex: 1 }}>
                        <span style={{ display: 'block', fontSize: 15, fontWeight: 600, color: INK, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {s.title}
                        </span>
                        {s.subtitle && (
                          <span style={{ display: 'block', fontSize: 12.5, color: '#78716c', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {s.subtitle}
                          </span>
                        )}
                      </span>
                      <span className="font-mono-x" style={{ fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#78716c', flexShrink: 0 }}>
                        {s.type}
                      </span>
                    </button>
                  ))
                ) : (
                  <div style={{ padding: '12px 18px', fontSize: 13.5, color: '#78716c' }}>
                    {suggestFetching ? 'Searching…' : `No quick matches — press Enter to search everything.`}
                  </div>
                )}
                <button
                  onClick={() => runSearch()}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    width: '100%',
                    textAlign: 'left',
                    background: '#fafaf9',
                    border: 'none',
                    borderTop: '1px solid #e7e5e4',
                    padding: '11px 18px',
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                    fontSize: 13.5,
                    fontWeight: 600,
                    color: TEAL_DARK,
                  }}
                >
                  🔍 Search everything for “{query.trim()}” →
                </button>
              </div>
            )}
          </div>

          {/* ── Trending questions (#151): the concrete, named policy questions
              lead the page — reviewers found them a stronger hook than the money
              banner. Same REAL /api/browse/top-items data as the Browse
              questions flyout; the row is hidden when there are none, and its
              label names the scope actually applied (state or nationwide). ── */}
          {(() => {
            const trending = (browseTopItems?.question ?? []).filter((q) => !!q.entity_name).slice(0, 5)
            if (trending.length === 0) return null
            return (
              <div className="v9-trending" style={{ maxWidth: 760, margin: '14px auto 0', textAlign: 'left' }}>
                <div className="font-mono-x" style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#c2410c', marginBottom: 8 }}>
                  <span aria-hidden="true">🔥 </span>Trending questions · {stateCode ? stateCode : 'Nationwide'}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {trending.map((q) => {
                    // Carry exactly the scope the label names: the list comes
                    // from a state-scoped query, so the link carries the state
                    // (never the saved city) — a "Nationwide" row carries none.
                    const p = new URLSearchParams()
                    if (stateCode) p.set('state', stateCode)
                    p.set('question_id', q.entity_id)
                    return (
                      <Link
                        key={q.entity_id}
                        to={`/policy-questions?${p.toString()}`}
                        state={{ fromHome: true }}
                        style={{ display: 'inline-block', padding: '8px 14px', borderRadius: 999, background: '#fff', border: '1px solid #fed7aa', color: INK, fontSize: 14, fontWeight: 600, lineHeight: 1.35, textDecoration: 'none' }}
                      >
                        {q.entity_name}
                      </Link>
                    )
                  })}
                </div>
              </div>
            )
          })()}

          {/* ── Browse pills: dropdown flyout previews, right under the search.
              Each pill previews its top ~5 items (questions/topics/causes) from
              the warehouse — no fabricated rows. ── */}
          <div className="v9-browse-pills">
            {[
              {
                key: 'questions' as const,
                name: 'Browse questions',
                icon: '⚖️',
                count: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.questions]?.transcript_count ?? null,
                hasTranscripts: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.questions]?.has_transcripts ?? true,
                order: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.questions]?.order ?? Number.MAX_SAFE_INTEGER,
                to: '/policy-questions',
                seeAllLabel: 'questions',
                desc: 'Open policy questions across jurisdictions.',
                header: '📌 Pinned questions',
                items: (browseTopItems?.question ?? [])
                  .filter((q) => !!q.entity_name)
                  .map((q) => ({
                    key: q.entity_id,
                    label: q.entity_name,
                    transcripts: q.transcript_count,
                    onSelect: () => {
                      const p = activeScopeParams()
                      p.set('question_id', q.entity_id)
                      navigate(`/policy-questions?${p.toString()}`, { state: { fromHome: true } })
                    },
                  })),
              },
              {
                key: 'topics' as const,
                name: 'Browse topics',
                icon: '🗂️',
                count: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.topics]?.transcript_count ?? null,
                hasTranscripts: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.topics]?.has_transcripts ?? true,
                order: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.topics]?.order ?? Number.MAX_SAFE_INTEGER,
                // Carry the ACTIVE scope into the Topics browse: city level
                // filters to the city, state level to the state, National (or
                // no location) → the full national catalog (#350).
                to: activeScopeParams().toString()
                  ? `/browse-topics?${activeScopeParams().toString()}`
                  : '/browse-topics',
                seeAllLabel: 'topics',
                desc: 'Everything discussed in public meetings.',
                header: 'Top topics',
                items: (browseTopItems?.topic ?? []).map((t) => ({
                  key: t.entity_id,
                  label: t.entity_name,
                  transcripts: t.transcript_count,
                  onSelect: () => {
                    const p = activeScopeParams()
                    p.set('topic_id', t.entity_id)
                    navigate(`/browse-topics?${p.toString()}`, { state: { fromHome: true } })
                  },
                })),
              },
              {
                key: 'causes' as const,
                name: 'Browse causes',
                icon: '💚',
                count: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.causes]?.transcript_count ?? null,
                hasTranscripts: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.causes]?.has_transcripts ?? true,
                order: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.causes]?.order ?? Number.MAX_SAFE_INTEGER,
                // Carry the ACTIVE scope into Browse Causes (same as Topics) so
                // the cause pills + decision cards land on the scope the user sees.
                to: activeScopeParams().toString()
                  ? `/browse-causes?${activeScopeParams().toString()}`
                  : '/browse-causes',
                seeAllLabel: 'causes',
                desc: 'Local nonprofits, grants & charitable work.',
                header: 'Top causes',
                items: (browseTopItems?.cause ?? []).map((c) => ({
                  key: c.entity_id,
                  label: c.entity_name,
                  transcripts: c.transcript_count,
                  onSelect: () => {
                    const p = activeScopeParams()
                    p.set('cause_id', c.entity_id)
                    navigate(`/browse-causes?${p.toString()}`, { state: { fromHome: true } })
                  },
                })),
              },
              {
                key: 'places' as const,
                name: 'Browse places',
                icon: '📍',
                count: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.places]?.transcript_count ?? null,
                hasTranscripts: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.places]?.has_transcripts ?? true,
                order: directoryCounts?.byType[BROWSE_CARD_ENTITY_TYPE.places]?.order ?? Number.MAX_SAFE_INTEGER,
                // Carry the ACTIVE scope into the Places browse so it lands
                // pre-filtered (e.g. city level "Atlanta" → ?state=GA&city=Atlanta).
                // National scope → plain /jurisdictions browse (#350).
                to: (() => {
                  const qs = activeScopeParams().toString()
                  return qs ? `/jurisdictions?${qs}` : '/jurisdictions'
                })(),
                seeAllLabel: 'places',
                desc: 'Cities, counties & districts with public records.',
                header: 'Top places',
                items: (browseTopItems?.place ?? []).map((p) => ({
                  key: p.entity_id,
                  label: p.entity_name,
                  transcripts: p.transcript_count,
                  onSelect: () => {
                    const params = new URLSearchParams()
                    if (p.state_code) params.set('state', p.state_code)
                    params.set('city', p.entity_name)
                    params.set('geoid', p.entity_id)
                    navigate(`/jurisdictions?${params.toString()}`, { state: { fromHome: true } })
                  },
                })),
              },
            ]
              // Order the cards to match the API's category ordering
              // (transcript_count desc, `place` pinned far right). Unknown/missing
              // entity types fall to the end via Number.MAX_SAFE_INTEGER.
              .slice()
              .sort((a, b) => a.order - b.order)
              .map((b) => {
              const open = browseOpen === b.key
              return (
                <div
                  key={b.key}
                  style={{ position: 'relative' }}
                  onMouseEnter={isTouch ? undefined : () => setBrowseOpen(b.key)}
                  onMouseLeave={isTouch ? undefined : () => setBrowseOpen((p) => (p === b.key ? null : p))}
                >
                  {/* One visual pill, two actions: the main area drills down to
                      the full page; the chevron toggles the preview combo. Hover
                      also opens the combo on desktop (handlers on the wrapper). */}
                  <div
                    style={{ display: 'flex', alignItems: 'stretch', background: '#fff', border: `1px solid ${open ? TEAL : '#e7e5e4'}`, boxShadow: open ? '0 4px 12px rgba(28,25,23,0.07)' : 'none', borderRadius: 999, overflow: 'hidden', transition: 'border-color 120ms ease, box-shadow 120ms ease' }}
                  >
                    <button
                      title={b.desc}
                      onClick={() => navigate(b.to, { state: { fromHome: true } })}
                      className="v9-browse-pill-main"
                      style={{ background: 'none', border: 'none', padding: '9px 6px 9px 10px', cursor: 'pointer', fontFamily: 'inherit', display: 'flex', alignItems: 'center', gap: 10 }}
                    >
                      <span className="font-display v9-browse-pill-label" style={{ fontSize: 16.5, fontWeight: 700, color: INK, whiteSpace: 'nowrap' }}>
                        {b.name}
                      </span>
                      {/* Badge = real distinct-transcript count for this
                          category (from /api/browse/summary). The unit is made
                          explicit so the number reads as transcripts, not an
                          ambiguous tally. Causes have no transcript linkage in
                          the data → honest em-dash, never a fabricated "0". */}
                      {b.hasTranscripts && b.count != null && b.count > 0 ? (
                        <span
                          className="font-mono-x"
                          title={`${b.count.toLocaleString('en-US')} meetings`}
                          aria-label={`${b.count.toLocaleString('en-US')} meetings`}
                          style={{ display: 'inline-flex', alignItems: 'baseline', gap: 4, fontSize: 11, fontWeight: 600, background: '#f5f5f4', border: '1px solid #e7e5e4', borderRadius: 999, padding: '1px 8px', color: '#57534e' }}
                        >
                          {b.count.toLocaleString('en-US')}
                          <span className="v9-browse-pill-badge-word" style={{ fontSize: 9.5, fontWeight: 600, color: '#78716c', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            meetings
                          </span>
                        </span>
                      ) : (
                        !b.hasTranscripts && (
                          <span
                            className="font-mono-x"
                            title="No linked transcripts yet"
                            aria-label="No linked transcripts yet"
                            style={{ fontSize: 11, fontWeight: 600, background: '#f5f5f4', border: '1px solid #e7e5e4', borderRadius: 999, padding: '1px 8px', color: '#78716c' }}
                          >
                            —
                          </span>
                        )
                      )}
                    </button>
                    <button
                      className="v9-browse-pill-chev"
                      aria-label={open ? `Hide top ${b.seeAllLabel}` : `Show top ${b.seeAllLabel}`}
                      aria-expanded={open}
                      aria-haspopup="true"
                      onClick={() => setBrowseOpen((p) => (p === b.key ? null : b.key))}
                      style={{ background: open ? '#f0fdfa' : 'none', border: 'none', borderLeft: '1px solid #f0efed', padding: '0 12px', cursor: 'pointer', fontFamily: 'inherit', color: TEAL_DARK, fontWeight: 700, fontSize: 11, display: 'flex', alignItems: 'center' }}
                    >
                      {open ? '▴' : '▾'}
                    </button>
                  </div>

                  {open && b.items.length > 0 && (
                    <div
                      role="menu"
                      aria-label={b.name}
                      style={{
                        position: 'absolute',
                        top: '100%',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        zIndex: 55,
                        width: b.key === 'questions' ? 330 : 280,
                        maxWidth: 'calc(100vw - 32px)',
                        // Transparent bridge over the gap so the cursor can travel
                        // from the pill into the menu without tripping mouseleave.
                        paddingTop: 6,
                        textAlign: 'left',
                      }}
                    >
                      <div
                        style={{
                          background: '#fff',
                          border: '1px solid #e7e5e4',
                          borderRadius: 12,
                          boxShadow: '0 10px 30px rgba(28,25,23,0.14)',
                          overflow: 'hidden',
                        }}
                      >
                        <div className="font-mono-x" style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: b.key === 'questions' ? '#c2410c' : '#78716c', padding: '11px 16px 7px' }}>
                          {b.header}
                        </div>
                        {b.items.map((it) => (
                          <button
                            key={it.key}
                            role="menuitem"
                            onClick={() => {
                              setBrowseOpen(null)
                              it.onSelect()
                            }}
                            style={{ display: 'flex', alignItems: 'center', gap: 9, width: '100%', textAlign: 'left', background: 'none', border: 'none', borderTop: '1px solid #f5f5f4', padding: '9px 16px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 13.5, color: INK }}
                            onMouseEnter={(e) => (e.currentTarget.style.background = '#fafaf9')}
                            onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                          >
                            {/* Wrap to at most two lines (then ellipsize) rather
                                than single-line truncation — question prompts are
                                full sentences and were getting cut mid-word.
                                minWidth:0 lets the flex child actually wrap. */}
                            <span
                              style={{
                                flex: 1,
                                minWidth: 0,
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                lineHeight: 1.35,
                              }}
                            >
                              {it.label}
                            </span>
                            {/* Real distinct-transcript count for this item
                                (from /api/browse/top-items). Shown for every
                                category including causes — causes are genuinely
                                0 (no transcript linkage), an honest real value. */}
                            <span
                              className="font-mono-x"
                              title={`${it.transcripts.toLocaleString('en-US')} transcripts`}
                              style={{ flexShrink: 0, display: 'inline-flex', alignItems: 'baseline', gap: 3, fontSize: 11, fontWeight: 600, color: '#78716c' }}
                            >
                              {it.transcripts.toLocaleString('en-US')}
                              <span style={{ fontSize: 9, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>tx</span>
                            </span>
                          </button>
                        ))}
                        <button
                          onClick={() => {
                            setBrowseOpen(null)
                            navigate(b.to, { state: { fromHome: true } })
                          }}
                          style={{ display: 'block', width: '100%', textAlign: 'left', background: '#fafaf9', border: 'none', borderTop: '1px solid #e7e5e4', padding: '10px 16px', cursor: 'pointer', fontFamily: 'inherit', fontSize: 12.5, fontWeight: 600, color: TEAL_DARK }}
                        >
                          {/* The badge count is a transcript count, not an
                              entity count, so it is intentionally omitted from
                              this "Browse all {entity}" label to avoid
                              mislabeling transcripts as the entity. */}
                          Browse all {b.seeAllLabel} →
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>

        </section>

        {/* ── Money hook (compact teal banner; REAL modal) — now the secondary
            CTA, below the hero and its trending questions (#151). ── */}
        <MoneyHookBanner />

        {/* ── Contested + Raised Eyebrows — two dedicated lens sections (REAL
            lens cards). The Contested header carries the single shared
            time-window selector, which drives both the lenses query and Money
            Moves below.

            Fallback: when this place HAS recent (analyzed) meetings but BOTH
            lenses come back empty — i.e. no analysis has surfaced a contested
            vote or a flagged pattern yet — we hide the two "No activity" cards
            and instead show the most recent meetings. That's a real, useful
            signal for the user rather than a pair of dead-end empty states.
            The shared time-window selector moves into that fallback header so
            Money Moves below always keeps its control. ── */}
        {(() => {
          const contestedLens = lensById['contested']
          const flagsLens = lensById['flags']
          const contestedCards =
            contestedLens && !contestedLens.placeholder ? contestedLens.cards.slice(0, 6) : []
          const flagsCards = flagsLens && !flagsLens.placeholder ? flagsLens.cards.slice(0, 6) : []
          // Only treat "empty" as real once the lenses query has resolved, so we
          // don't flash the meetings fallback while the lenses are still loading.
          const lensesEmpty = !!lensesData && contestedCards.length === 0 && flagsCards.length === 0
          const showRecentFallback = lensesEmpty && recentMeetings.length > 0

          // The single shared time-window selector — rendered in whichever
          // section heads the block so Money Moves below always has its control.
          const whenSelector = (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginLeft: 'auto' }}>
              {WHEN.map((w) => (
                <Chip key={w.label} active={!!lensesData && when.window === w.window} onClick={() => setWhen(w)}>
                  {w.label}
                </Chip>
              ))}
            </div>
          )

          if (showRecentFallback) {
            const fmtMeetingDate = (iso: string | null): string => {
              if (!iso) return ''
              const d = new Date(`${iso}T00:00:00`)
              return Number.isNaN(d.getTime())
                ? ''
                : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
            }
            return (
              <section style={{ marginTop: 30 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: '#eff6ff', display: 'grid', placeItems: 'center', fontSize: 21 }}>
                    🗓️
                  </div>
                  <div style={{ flex: 1, minWidth: 200 }}>
                    <h2 className="font-display" style={{ fontSize: 22, fontWeight: 700, margin: 0, color: '#2563eb' }}>
                      Recent meetings
                    </h2>
                    <div style={{ fontSize: 14, color: '#78716c' }}>The latest meetings, analyzed or not yet · 📍 {placeLabel}</div>
                  </div>
                  {whenSelector}
                </div>

                <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
                  {recentMeetings.map((m) => {
                    const place = [m.city || m.jurisdiction || '', m.state_code].filter(Boolean).join(', ')
                    const date = fmtMeetingDate(m.date)
                    const analyzed = m.analyzed !== false
                    const href = meetingHref(m)
                    const open = () => {
                      if (!href) return
                      if (/^https?:\/\//.test(href)) window.open(href, '_blank', 'noopener,noreferrer')
                      else navigate(href, { state: { fromHome: true } })
                    }
                    return (
                      <button
                        key={m.meeting_id ?? `video-${m.video_id}`}
                        onClick={open}
                        style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', background: '#fff', border: '1px solid #e7e5e4', borderRadius: 14, padding: 0, overflow: 'hidden', cursor: 'pointer', fontFamily: 'inherit' }}
                      >
                        {m.video_id && (
                          <MeetingThumbnail
                            videoId={m.video_id}
                            alt={m.title ?? undefined}
                            place={place}
                            date={m.date}
                            kind={inferThumbnailKind(m.title)}
                          />
                        )}
                        <div style={{ padding: '14px 16px' }}>
                          {!analyzed && (
                            <span style={{ display: 'inline-block', marginBottom: 6, fontSize: 10.5, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#57534e', background: '#f5f5f4', borderRadius: 999, padding: '2px 9px' }}>
                              {NOT_ANALYZED}
                            </span>
                          )}
                          <div className="clamp2" style={{ fontSize: 15, fontWeight: 700, color: INK, lineHeight: 1.3 }}>
                            {m.title || 'Untitled meeting'}
                          </div>
                          <div style={{ marginTop: 6, fontSize: 12.5, color: '#78716c', display: 'flex', flexWrap: 'wrap', gap: '2px 10px' }}>
                            {place && <span>📍 {place}</span>}
                            {date && <span>{date}</span>}
                          </div>
                          {!analyzed && m.evidence && (
                            <div style={{ marginTop: 8 }}>
                              {m.evidence_label && (
                                <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#5f6b66' }}>
                                  Mentions · {m.evidence_label}
                                </div>
                              )}
                              <div className="clamp2" style={{ marginTop: 2, fontSize: 13, color: '#56635e', lineHeight: 1.35 }}>
                                {highlightSnippet(m.evidence)}
                              </div>
                            </div>
                          )}
                          {analyzed && m.decision_count > 0 && (
                            <div style={{ marginTop: 8 }}>
                              <span style={{ display: 'inline-block', fontSize: 11.5, fontWeight: 600, color: TEAL_DARK, background: '#ecfdf5', borderRadius: 999, padding: '2px 9px' }}>
                                {m.decision_count} {m.decision_count === 1 ? 'decision' : 'decisions'}
                              </span>
                            </div>
                          )}
                        </div>
                      </button>
                    )
                  })}
                </div>
              </section>
            )
          }

          const renderLens = (id: 'contested' | 'flags', withSelector: boolean) => {
            const meta = SIGNAL_META[id]
            const cards = id === 'contested' ? contestedCards : flagsCards
            return (
              <section style={{ marginTop: 30 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: meta.bg, display: 'grid', placeItems: 'center', fontSize: 21 }}>
                    {meta.icon}
                  </div>
                  <div style={{ flex: 1, minWidth: 200 }}>
                    <h2 className="font-display" style={{ fontSize: 22, fontWeight: 700, margin: 0, color: meta.color }}>
                      {meta.name}
                    </h2>
                    <div style={{ fontSize: 14, color: '#78716c' }}>{meta.desc} · 📍 {placeLabel}</div>
                  </div>
                  {withSelector && whenSelector}
                </div>

                <div style={{ marginTop: 16 }}>
                  {id === 'flags' && cards.length > 0 && (
                    <div
                      style={{
                        marginBottom: 10,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        borderRadius: 999,
                        border: '1px solid #ddd6fe',
                        background: '#f5f3ff',
                        color: '#5b21b6',
                        fontSize: 11.5,
                        fontWeight: 600,
                        padding: '5px 10px',
                      }}
                    >
                      Manual human review recommended
                    </div>
                  )}
                  {cards.length > 0 ? (
                    <LensCarousel
                      cards={cards}
                      lens={{ id, em: meta.icon, label: meta.name, clr: meta.color }}
                      unscoped={national}
                    />
                  ) : (
                    <div style={{ background: '#fff', border: '1px solid #e7e5e4', borderRadius: 14, padding: '28px 16px', textAlign: 'center', color: '#78716c', fontSize: 14 }}>
                      No {meta.name} activity in {placeLabel} for {when.label.toLowerCase()}.
                    </div>
                  )}
                </div>
              </section>
            )
          }

          // "What's New" — the most recent meetings in this place, rendered in
          // the same tiles the topic lenses use, regardless of whether each
          // meeting produced a decision. Sits at the top of the block in the
          // normal case; in the empty-lenses fallback the "Recent meetings" grid
          // above already covers these, so we don't double up.
          const whatsNewCards = recentMeetings.map(meetingToCard)
          const whatsNewSection =
            whatsNewCards.length > 0 ? (
              <section style={{ marginTop: 30 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: '#eff6ff', display: 'grid', placeItems: 'center', fontSize: 21 }}>
                    🗓️
                  </div>
                  <div style={{ flex: 1, minWidth: 200 }}>
                    <h2 className="font-display" style={{ fontSize: 22, fontWeight: 700, margin: 0, color: '#2563eb' }}>
                      What&rsquo;s New
                    </h2>
                    <div style={{ fontSize: 14, color: '#78716c' }}>
                      The most recent meetings, including ones not yet analyzed · 📍 {placeLabel}
                    </div>
                  </div>
                </div>
                <div style={{ marginTop: 16 }}>
                  <LensCarousel
                    cards={whatsNewCards}
                    lens={{ id: 'whats-new', em: '🗓️', label: "What's New", clr: '#2563eb' }}
                    unscoped={national}
                  />
                </div>
              </section>
            ) : null

          return (
            <>
              {whatsNewSection}
              {renderLens('contested', true)}
              {renderLens('flags', false)}
            </>
          )
        })()}

        {/* ── Money Moves — compact one-line summary (REAL /api/money-flow
            headline figure) that drills down into the full tabbed Sankey in a
            modal, so it no longer dominates the page. ── */}
        <section style={{ marginTop: 30, paddingBottom: 44 }}>
          <MoneyMovesTeaser
            national={national}
            stateCode={stateCode}
            city={city}
            county={location?.county || undefined}
            window={when.window}
            placeLabel={placeLabel}
          />
        </section>
      </div>


      {/* ── How It Works (ported from the original home page, restyled for v9).
          Header format matches the sibling "Our Impact" section: section name as
          the centered <h2>, no mono eyebrow. ── */}
      <section id="how-it-works" className="v9-section-full" style={{ background: '#fff', borderTop: '1px solid #e7e5e4', padding: '40px 24px', scrollMarginTop: 72 }}>
        <div style={{ maxWidth: 1180, margin: '0 auto' }}>
          <div style={{ textAlign: 'center', maxWidth: 720, margin: '0 auto 18px' }}>
            <h2 className="font-display" style={{ fontSize: 'clamp(26px, 3.6vw, 34px)', fontWeight: 800, margin: 0, color: INK }}>
              How it works
            </h2>
            <p style={{ fontSize: 15, color: '#57534e', lineHeight: 1.45, marginTop: 8 }}>
              Take real action on local issues — starting with your personal impact. Choose a cause, make a plan,
              find help when someone needs direct support, track the decisions that matter, and build on open data.
            </p>
          </div>

          <StepZeroImpact />

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, alignItems: 'stretch' }}>
            {([
              {
                icon: '📍', title: 'Choose a cause, topic, place or question', hash: 'explore-causes',
                items: [
                  { kind: 'check', label: 'School Quality' },
                  { kind: 'check', label: 'Property Taxes' },
                  // The reader's own place (#1047), never a hard-coded one.
                  { kind: 'check', label: location?.city ? `${location.city} Schools` : 'Local Schools' },
                  { kind: 'check', label: 'Traffic & Roads' },
                  { kind: 'arrow', label: 'Why are my taxes rising?' },
                ],
              },
              {
                icon: '💚', title: 'Find help & allies', hash: 'explore-find-help',
                items: [
                  { kind: 'check', label: 'Find Allies on Issues' },
                  { kind: 'check', label: 'Neighborhood Groups' },
                  { kind: 'check', label: 'Advocacy Support' },
                  { kind: 'check', label: 'Local Networks' },
                  { kind: 'arrow', label: 'Family Resources' },
                ],
              },
              {
                icon: '📊', title: 'Track decisions', hash: 'explore-track-decisions',
                items: [
                  { kind: 'check', label: 'School Board Votes' },
                  { kind: 'check', label: 'Neighborhood Changes' },
                  { kind: 'check', label: 'Public Safety' },
                  { kind: 'check', label: 'New Developments Near Me' },
                ],
              },
              {
                icon: '🧩', title: 'Build with data', hash: 'explore-build',
                items: [
                  { kind: 'check', label: 'Local Trends' },
                  { kind: 'check', label: 'Impact Maps' },
                  { kind: 'arrow', label: 'Easy Tools' },
                ],
              },
            ] as { icon: string; title: string; hash: string; items: { kind: 'check' | 'arrow' | 'note'; label: string }[] }[]).map((step) => (
              <button
                key={step.title}
                onClick={() => navigate(`/explore#${step.hash}`)}
                style={{ textAlign: 'left', background: '#fff', border: '1px solid #e7e5e4', borderRadius: 14, padding: 15, cursor: 'pointer', fontFamily: 'inherit', display: 'flex', flexDirection: 'column', gap: 0, boxShadow: '0 1px 2px rgba(28,25,23,0.04)' }}
              >
                <span style={{ width: 36, height: 36, borderRadius: 10, background: '#f0fdfa', display: 'grid', placeItems: 'center', fontSize: 18, marginBottom: 9 }}>
                  {step.icon}
                </span>
                <span className="font-display" style={{ fontSize: 16, fontWeight: 700, color: INK, lineHeight: 1.25 }}>{step.title}</span>
                <ul style={{ listStyle: 'none', margin: '9px 0 0', padding: 0, display: 'flex', flexDirection: 'column', gap: 5 }}>
                  {step.items.map((it) => (
                    <li
                      key={it.label}
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 7,
                        fontSize: 13,
                        lineHeight: 1.4,
                        color: it.kind === 'arrow' ? TEAL_DARK : it.kind === 'note' ? '#78716c' : '#44403c',
                        fontWeight: it.kind === 'arrow' ? 700 : it.kind === 'note' ? 600 : 400,
                      }}
                    >
                      <span aria-hidden style={{ flexShrink: 0, color: it.kind === 'arrow' ? TEAL_DARK : it.kind === 'note' ? '#78716c' : '#047857', fontWeight: 700 }}>
                        {it.kind === 'arrow' ? '→' : it.kind === 'note' ? '•' : '✓'}
                      </span>
                      <span>{it.label}</span>
                    </li>
                  ))}
                </ul>
              </button>
            ))}
          </div>

          <div style={{ textAlign: 'center', marginTop: 18, fontSize: 15, color: '#57534e' }}>
            <span style={{ fontWeight: 700, color: INK }}>Ready to act?</span>{' '}
            Show up at meetings · Write letters · Change the process
          </div>
        </div>
      </section>

      {/* ── Our Impact / Our Mission (ported from the original home page) ── */}
      <section id="impact" className="v9-section-full" style={{ background: '#fafaf9', borderTop: '1px solid #e7e5e4', padding: '56px 24px', scrollMarginTop: 72 }}>
        <div style={{ maxWidth: 1180, margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: 32 }}>
            <h2 className="font-display" style={{ fontSize: 'clamp(26px, 3.6vw, 34px)', fontWeight: 800, margin: 0, color: INK }}>
              Our Impact
            </h2>
            <p style={{ fontSize: 16, color: '#57534e', margin: '12px auto 18px', maxWidth: 640 }}>
              One platform connecting residents, leaders, and funders to what&apos;s really happening on the ground.
            </p>
            <button
              onClick={() => setShowStrategicPlan(true)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: TEAL, color: '#fff', border: 'none', borderRadius: 999, padding: '11px 22px', fontSize: 14.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
            >
              📄 View Our Strategic Plan
            </button>
          </div>

          <div style={{ maxWidth: 720, margin: '0 auto', textAlign: 'center', background: '#fff', border: '1px solid #e7e5e4', borderRadius: 18, padding: '36px 28px' }}>
            <h3 className="font-display" style={{ fontSize: 'clamp(22px, 3vw, 28px)', fontWeight: 800, margin: 0, color: INK }}>
              Our Mission
            </h3>
            <p style={{ fontSize: 15, color: '#57534e', margin: '10px 0 14px', fontWeight: 600 }}>
              CommunityOne: One Map for Every Community
            </p>
            <p style={{ fontSize: 15.5, color: '#44403c', lineHeight: 1.6, marginBottom: 12 }}>
              Every person deserves to find the help they need and have a voice in the decisions that shape their lives.
              But public resources are scattered, gaps go unseen, and communities are left navigating alone.
            </p>
            <p style={{ fontSize: 15.5, color: '#44403c', lineHeight: 1.6, marginBottom: 22 }}>
              CommunityOne changes that. One platform connects residents, leaders, and funders to what&apos;s really
              happening on the ground — so no community has to fight just to be seen.
            </p>
            <button
              onClick={() => navigate('/explore')}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 8, background: INK, color: '#fff', border: 'none', borderRadius: 10, padding: '11px 20px', fontSize: 14.5, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}
            >
              Start Exploring →
            </button>
          </div>
        </div>
      </section>

      {/* ── The thesis, under Impact (#995). ── */}
      <section className="v9-section-full" aria-labelledby="home-thesis-h" style={{ background: '#fff', borderTop: '1px solid #e7e5e4', padding: '52px 24px', textAlign: 'center' }}>
        <h2 id="home-thesis-h" className="font-display" style={{ fontSize: 'clamp(32px, 5vw, 52px)', fontWeight: 900, margin: 0, lineHeight: 1.05, letterSpacing: '-0.02em', color: INK }}>
          Every local decision, in one place.
        </h2>
        <p style={{ fontSize: 'clamp(16px, 2vw, 19px)', fontWeight: 500, color: '#57534e', maxWidth: 760, margin: '16px auto 0', lineHeight: 1.5 }}>
          Search the meetings, votes, spending, and debates shaping your community.
          <br />
          Free, forever.
        </p>
      </section>

      {/* Strategic Plan PDF — lightweight modal (real PDF in public/pdf). */}
      {showStrategicPlan && (
        <div
          onClick={() => setShowStrategicPlan(false)}
          style={{ position: 'fixed', inset: 0, zIndex: 70, background: 'rgba(15,43,43,0.5)', backdropFilter: 'blur(2px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ width: '100%', maxWidth: 980, height: '85vh', background: '#fff', borderRadius: 18, overflow: 'hidden', display: 'flex', flexDirection: 'column', boxShadow: '0 20px 50px rgba(0,0,0,0.3)' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: '1px solid #e7e5e4' }}>
              <span className="font-display" style={{ fontSize: 16, fontWeight: 700, color: INK }}>
                📄 CommunityOne Strategic Plan
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <a href="/pdf/c1_strategic_plan.pdf" target="_blank" rel="noopener noreferrer" style={{ fontSize: 13, fontWeight: 600, color: TEAL_DARK }}>
                  Open in new tab
                </a>
                <button onClick={() => setShowStrategicPlan(false)} aria-label="Close" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 18, color: '#78716c', lineHeight: 1 }}>
                  ✕
                </button>
              </div>
            </div>
            <iframe src="/pdf/c1_strategic_plan.pdf" title="CommunityOne Strategic Plan" style={{ flex: 1, width: '100%', border: 'none' }} />
          </div>
        </div>
      )}

      </main>
      <SiteFooter />
    </div>
  )
}
