import { Link } from 'react-router-dom'
import type { RankingPlace } from '../../api/rankings'
import { BAND_SHORT, dateLabel, evidenceHref, sided } from '../../utils/rankings'

const OFFICIALS: Record<string, string> = { for: 'mostly for', against: 'mostly against', split: 'split' }

export default function PlacePanel({ place, topicId, topicName, onClose }: { place: RankingPlace; topicId: number; topicName: string; onClose: () => void }) {
  return (
    <section className="mt-3 rounded-lg border border-gray-300 bg-white p-3 text-sm" data-testid="place-panel" aria-label={`${place.jurisdiction_name}, ${place.state_code} on ${topicName}`}>
      <div className="flex items-start justify-between gap-2">
        <h4 className="m-0 text-base font-semibold">{place.jurisdiction_name}, {place.state_code}</h4>
        <button type="button" onClick={onClose} className="rounded px-2 py-1 text-gray-600 hover:bg-gray-100" aria-label="Close place panel">Close</button>
      </div>
      <p className="my-1 text-gray-600">
        {place.size_band === 'unknown' ? 'Size not known' : `${BAND_SHORT[place.size_band][0].toUpperCase()}${BAND_SHORT[place.size_band].slice(1)} place`}
        {place.population != null ? ` · population ${place.population.toLocaleString('en-US')}` : ''}
      </p>
      <p className="my-1">
        <b>{place.speakers_against}</b> against, <b>{place.speakers_for}</b> for ({sided(place)} speakers), across <b>{place.meetings}</b> {place.meetings === 1 ? 'meeting' : 'meetings'}. Last meeting: {dateLabel(place.last_meeting_date)}.
      </p>
      {place.is_ranked && place.band_rank != null && place.band_ranked_count != null ? (
        <p className="my-1">Ranked #{place.band_rank} of {place.band_ranked_count} {BAND_SHORT[place.size_band]} places (1 = most against).</p>
      ) : (
        <p className="my-1 text-gray-600">Too few speakers to rank: a place needs at least 10 speakers across 2 or more meetings in 24 months.</p>
      )}
      {place.officials_side != null && <p className="my-1">Officials matched to the roster: {OFFICIALS[place.officials_side]}.</p>}
      <Link to={evidenceHref(topicId, place)} className="font-medium text-primary-700 hover:underline">
        See the meetings on {topicName} in {place.jurisdiction_name}
      </Link>
    </section>
  )
}
