/**
 * Meeting Q&A chat (#630 / #652 / #670) — right-docked panel (not full-screen).
 * Scope from URL (?state=&city=&county_fips=); label matches the filter.
 */
import { useSearchParams } from 'react-router-dom'
import { EnvelopeIcon } from '@heroicons/react/24/outline'
import { contactMailto } from '../utils/contact'
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
    <MeetingChatRuntimeProvider scope={scope}>
      <div className="flex min-h-[calc(100dvh-5rem)] flex-1 justify-end bg-slate-300 p-3 sm:p-4">
        <div
          className="flex h-[min(38rem,calc(100dvh-6.5rem))] w-full max-w-xl flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg"
          role="region"
          aria-label="Chat and contact"
        >
          {/* Contact option on top of the chat (#860): the chat answers from meeting records; a person answers email. */}
          <div className="flex shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-xs text-slate-600">
              The chat answers from meeting records. Need a person, or have feedback?
            </p>
            <a
              href={contactMailto('Question about Open Navigator')}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-primary-600 shadow-sm hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-600"
            >
              <EnvelopeIcon className="h-4 w-4" aria-hidden="true" />
              Contact us
            </a>
          </div>
          <div className="flex min-h-0 flex-1">
            <div className="flex min-h-0 min-w-0 flex-1 flex-col">
              <MeetingChatThread />
            </div>
            <MeetingChatSidebar scopeLabel={label} />
          </div>
        </div>
      </div>
    </MeetingChatRuntimeProvider>
  )
}
