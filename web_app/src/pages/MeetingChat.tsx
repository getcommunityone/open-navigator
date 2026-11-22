/**
 * Meeting Q&A chat (#630 / #652 / #670) — thread main + right rail.
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

/** Matches Layout’s content band under SiteHeader (`min-h-[calc(100dvh-5rem)]`). */
const CHAT_VIEWPORT_H = 'h-[calc(100dvh-5rem)]'

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
    <MeetingChatRuntimeProvider scope={scope}>
      <div className={`flex min-h-0 flex-1 overflow-hidden bg-white ${CHAT_VIEWPORT_H}`}>
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <MeetingChatThread />
        </div>
        <MeetingChatSidebar scopeLabel={label} />
      </div>
    </MeetingChatRuntimeProvider>
  )
}
