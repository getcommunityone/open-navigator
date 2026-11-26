import { useState } from 'react'

// #798: a quiet "how this summary was made" line at the bottom of the decision page. Click opens a
// panel of recorded facts only. A fact the run did not record is left out, never filled in.

export interface Provenance {
  model?: string | null
  generated_at?: string | null
  tier?: string | null
  prompt_name?: string | null
  prompt_version?: string | null
  transcript_source?: string | null
  video_url?: string | null
  analyses_for_meeting?: number | null
}

export interface ProvenanceFact {
  label: string
  value: string
}

const TIER_LABEL: Record<string, string> = {
  light: 'Light (fast, shorter analysis)',
  full: 'Full (deeper analysis)',
}

/** The facts to list, in order, skipping every one that was not recorded. */
export function provenanceFacts(p: Provenance | null | undefined): ProvenanceFact[] {
  if (!p) return []
  const out: ProvenanceFact[] = []
  if (p.model) out.push({ label: 'Model', value: p.model })
  if (p.generated_at) {
    const d = new Date(p.generated_at)
    if (!Number.isNaN(d.getTime())) out.push({ label: 'Generated', value: d.toLocaleString() })
  }
  if (p.tier && TIER_LABEL[p.tier]) out.push({ label: 'Analysis', value: TIER_LABEL[p.tier] })
  if (p.prompt_name)
    out.push({
      label: 'Prompt',
      value: p.prompt_version ? `${p.prompt_name} (version ${p.prompt_version})` : p.prompt_name,
    })
  if (p.transcript_source) out.push({ label: 'Transcript source', value: p.transcript_source })
  return out
}

/** Set when the preferred-analysis step chose between several analyses of this meeting. */
export function chosenAmongNote(p: Provenance | null | undefined): string | null {
  const n = p?.analyses_for_meeting
  if (!n || n < 2) return null
  return `This meeting has ${n} analyses. This is the one shown, chosen by the site's model preference.`
}

export default function AnalysisProvenance({ provenance }: { provenance?: Provenance | null }) {
  const [open, setOpen] = useState(false)
  const facts = provenanceFacts(provenance)
  const note = chosenAmongNote(provenance)
  const video = provenance?.video_url || null
  if (!facts.length && !video) return null

  return (
    <div className="mt-2 text-[12px] text-gray-400" data-testid="analysis-provenance">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="text-gray-400 underline decoration-dotted underline-offset-2 hover:text-gray-500"
      >
        AI-assisted summary · {open ? 'hide details' : 'details'}
      </button>
      {open ? (
        <div className="mt-2 rounded-lg border border-gray-200 bg-white/70 p-3 leading-relaxed text-gray-500">
          <p>
            This summary is machine-generated from the meeting transcript. It can contain mistakes: check it
            against the recording.
          </p>
          {facts.length ? (
            <dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
              {facts.map((f) => (
                <div key={f.label} className="contents">
                  <dt className="text-gray-400">{f.label}</dt>
                  <dd className="break-words text-gray-600">{f.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          {note ? <p className="mt-2">{note}</p> : null}
          {video ? (
            <p className="mt-2">
              <a href={video} target="_blank" rel="noreferrer" className="text-teal-700 hover:underline">
                Watch the source recording
              </a>
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
