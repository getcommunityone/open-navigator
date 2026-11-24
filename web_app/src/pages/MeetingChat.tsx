/**
 * Meeting Q&A chat (#630 / #652 / #670) — right-docked panel (not full-screen).
 * Scope from URL (?state=&city=&county_fips=); label matches the filter.
 */
import { useCallback, useEffect } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { EnvelopeIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { closeChatTarget, contactMailto } from '../utils/contact'
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

  // Close (#879): back to where the visitor came from, or home when the chat was the first page opened.
  const navigate = useNavigate()
  const location = useLocation()
  const close = useCallback(() => {
    const target = closeChatTarget(location.key)
    if (target === -1) navigate(-1)
    else navigate(target)
  }, [navigate, location.key])

  // Escape closes too, except while a message is being typed: then it would throw the draft away.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      const el = e.target as HTMLElement | null
      const typing =
        !!el && (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT' || el.isContentEditable) &&
        ((el as HTMLInputElement).value ?? el.textContent ?? '').trim() !== ''
      if (!typing) close()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [close])

  return (
    <MeetingChatRuntimeProvider scope={scope}>
      <div className="flex min-h-[calc(100dvh-5rem)] flex-1 justify-end page-bg p-0 sm:p-4">
        <div
          className="flex h-[calc(100dvh-5rem)] w-full flex-col overflow-hidden border-slate-200 bg-white sm:h-[min(38rem,calc(100dvh-6.5rem))] sm:max-w-xl sm:rounded-xl sm:border sm:shadow-lg"
          role="region"
          aria-label="Chat and contact"
        >
          {/* Contact option on top of the chat (#860): the chat answers from meeting records; a person answers email. */}
          <div className="flex shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-xs text-slate-600">
              The chat answers from meeting records. Need a person, or have feedback?
            </p>
            <div className="flex items-center gap-2">
            <a
              href={contactMailto('Question about Open Navigator')}
              className="inline-flex items-center gap-1.5 min-h-[44px] rounded-lg border border-slate-300 bg-white px-3 py-1 text-xs font-semibold sm:min-h-0 sm:px-2.5 text-primary-600 shadow-sm hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-600"
            >
              <EnvelopeIcon className="h-4 w-4" aria-hidden="true" />
              Contact us
            </a>
            <button
              type="button"
              onClick={close}
              aria-label="Close chat"
              title="Close chat (Esc)"
              className="inline-flex h-11 w-11 items-center sm:h-7 sm:w-7 justify-center rounded-lg border border-slate-300 bg-white text-slate-700 shadow-sm hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-600"
            >
              <XMarkIcon className="h-4 w-4" aria-hidden="true" />
            </button>
            </div>
          </div>
          <div className="flex min-h-0 flex-1 flex-col-reverse sm:flex-row">
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
