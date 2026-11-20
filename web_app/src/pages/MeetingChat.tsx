/**
 * Meeting Q&A chat (#630 / #652) — ChatGPT-style sidebar + thread.
 * Scope from URL (?state=&city=&county_fips=); label matches the filter.
 */
import { useSearchParams } from 'react-router-dom'
import { expandStateName } from '../utils/formatters'
import {
  MeetingChatRuntimeProvider,
  type MeetingChatScope,
} from '../components/meeting-chat/MeetingChatRuntime'
import { MeetingChatSidebar } from '../components/meeting-chat/MeetingChatSidebar'
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

  return (
    <div className="flex min-h-0 flex-1 overflow-hidden bg-white">
      <MeetingChatRuntimeProvider scope={scope}>
        <MeetingChatSidebar scopeLabel={label} />
        <div className="flex min-w-0 flex-1 flex-col">
          <MeetingChatThread />
        </div>
      </MeetingChatRuntimeProvider>
    </div>
  )
}
