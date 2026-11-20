/**
 * Public meeting Q&A chat (#630) — assistant-ui thread + FastAPI summaries path.
 * Scope comes from URL (?state=&city=&county_fips=) so the label matches the filter.
 */
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowLeftIcon } from '@heroicons/react/24/outline'
import { expandStateName } from '../utils/formatters'
import {
  MeetingChatRuntimeProvider,
  type MeetingChatScope,
} from '../components/meeting-chat/MeetingChatRuntime'
import { MeetingChatThread } from '../components/meeting-chat/MeetingChatThread'

function scopeLabel(scope: MeetingChatScope): string {
  if (scope.city && scope.state) {
    return `${scope.city}, ${expandStateName(scope.state) || scope.state}`
  }
  if (scope.state) {
    return expandStateName(scope.state) || scope.state
  }
  if (scope.county_fips) {
    return `County ${scope.county_fips}`
  }
  return 'National'
}

export default function MeetingChat() {
  const [params] = useSearchParams()
  const scope: MeetingChatScope = {
    state: params.get('state') || undefined,
    city: params.get('city') || undefined,
    county_fips: params.get('county_fips') || undefined,
  }
  const label = scopeLabel(scope)
  const searchBack = params.toString() ? `?${params.toString()}` : ''

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-3xl flex-col px-4 py-6">
      <div className="mb-4 flex items-center gap-3">
        <Link
          to={`/search${searchBack}`}
          className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-primary-700"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          Search
        </Link>
        <h1 className="font-serif text-2xl text-slate-900">Meeting chat · {label}</h1>
      </div>

      <div className="flex-1 overflow-hidden rounded-2xl border border-slate-200 shadow-sm">
        <MeetingChatRuntimeProvider scope={scope}>
          <MeetingChatThread scopeLabel={label} />
        </MeetingChatRuntimeProvider>
      </div>
    </div>
  )
}
