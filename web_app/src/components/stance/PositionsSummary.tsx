import { useId, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchTopicCaptionFacts } from '../../api/topics'
import { fetchDataCenterDecisions } from '../../api/dataCenters'
import { storyScopeLabel, type StoryScope } from '../../utils/dataStory'
import {
  disagreementLine,
  disagreementParts,
  namedSides,
  namedSidesClause,
  officialPositionsLine,
  publicPositionsLine,
  recordedEvidence,
  speakersOwnWordsLine,
} from '../../utils/stanceEvidence'
import { topicPositions } from '../../utils/topicPositions'
import { DrillValue, KpiDrillSheet } from './KpiDrill'

/**
 * Who took which side, named by who (#1330, owner: "I thought we were counting all speakers and highlighting where they
 * disagree"): the public's positions read, officials' positions read with their recorded votes and the people named on each
 * side of a decision, and where officials sided against the public, with a tap through to those meetings. Every number is
 * from the caption facts and the decisions list for exactly this scope; a line with nothing behind it is left out.
 */
export default function PositionsSummary({
  scope,
  only,
  headlined = false,
}: {
  scope: StoryScope
  /** The Overview shows only the disagreement line. */
  only?: 'disagreement'
  /** The screen's headline already says it (Who spoke up): the line here is only the way into the meetings. */
  headlined?: boolean
}) {
  const city = scope.stateCode ? (scope.city ?? '') : ''
  const factsQ = useQuery({
    queryKey: ['caption-facts', 'data-centers', scope.stateCode ?? '', city],
    queryFn: () => fetchTopicCaptionFacts('data-centers', scope.stateCode ?? undefined, scope.city),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const decisionsQ = useQuery({
    queryKey: ['dc-decisions-named', scope.stateCode ?? '', city],
    queryFn: () => fetchDataCenterDecisions({ state: scope.stateCode ?? undefined, city: city || undefined, limit: 500 }),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const [open, setOpen] = useState(false)
  const sheetId = useId()
  if (!factsQ.data) return null
  const e = recordedEvidence(factsQ.data)
  const label = storyScopeLabel(scope)
  const where = scope.stateName ? `In ${label}` : 'Across America'
  const pub = publicPositionsLine(e)
  const own = speakersOwnWordsLine(e, topicPositions('data-centers'))
  // Named people only from a complete list: a capped list would undercount and still read as the scope's total.
  const dec = decisionsQ.data
  const complete = Boolean(dec && dec.counts.contested != null && dec.counts.uncontested != null && dec.items.length >= dec.counts.contested + dec.counts.uncontested)
  const named = complete && dec ? namedSidesClause(namedSides(dec.items)) : null
  const off = officialPositionsLine(e)
  const officials = off ? [off, named].filter(Boolean).join('; ') : named ? `Officials: ${named}` : null
  const dis = disagreementLine(e, where)
  const parts = disagreementParts(e, where)
  if (only === 'disagreement' ? !dis : !pub && !own && !officials && !dis) return null
  const n = e.disagreement ?? 0
  return (
    <div className="stance-positions-summary" data-testid="positions-summary">
      {!only && pub && <p className="stance-positions-who">{pub}</p>}
      {!only && own && <p className="stance-positions-who" data-testid="positions-own-words">{own}</p>}
      {!only && officials && <p className="stance-positions-who">{officials}</p>}
      {dis && headlined && (
        <p className="stance-positions-disagree" data-testid="positions-disagreement">
          <DrillValue text label="meetings where officials sided against the public" open={open} controls={sheetId} onToggle={() => setOpen((o) => !o)}>
            {`Show the ${n.toLocaleString('en-US')} ${n === 1 ? 'meeting' : 'meetings'} where officials sided against the public`}
          </DrillValue>
        </p>
      )}
      {dis && !headlined && (
        <p className="stance-positions-disagree" data-testid="positions-disagreement">
          {/* The count is the tap target; the sentence reads the same with or without it. */}
          {parts!.before}
          <DrillValue text label="meetings where officials sided against the public" open={open} controls={sheetId} onToggle={() => setOpen((o) => !o)}>
            {parts!.count}
          </DrillValue>
          {parts!.after}
        </p>
      )}
      {open && (
        <KpiDrillSheet
          id={sheetId}
          drill={{ kind: 'disagreement' }}
          title="Officials sided against the public"
          scope={{ stateCode: scope.stateCode, city: scope.city }}
          scopeLabel={label}
          onClose={() => setOpen(false)}
        />
      )}
      {!only && <p className="stance-note">
        Positions are read from each meeting&apos;s transcript, one reading per meeting; speakers&apos; own words are read one
        speaker at a time by a classifier, confident readings only; named people are from each decision&apos;s record; votes are
        by which way each decision went.
      </p>}
    </div>
  )
}
