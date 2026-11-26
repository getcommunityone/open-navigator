/**
 * Meeting chat thread rail (#652 / #670): New chat, scope, recent threads — right side, light.
 */
import { useState } from 'react'
import { ChevronDownIcon, PlusIcon, TrashIcon } from '@heroicons/react/24/outline'
import { useMeetingChatControls } from './MeetingChatRuntime'

export function MeetingChatSidebar({ scopeLabel }: { scopeLabel: string }) {
  const { threads, activeId, newChat, selectThread, deleteThread, isRunning } =
    useMeetingChatControls()
  // On a phone the rail is a bar above the conversation (#907); recent chats open from the "Recent" control.
  const [recentOpen, setRecentOpen] = useState(false)

  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-slate-200 bg-slate-50 text-slate-800 sm:h-full sm:w-44 sm:border-b-0 sm:border-l">
      <div className="flex items-center gap-2 px-3 py-2 sm:block sm:border-b sm:border-slate-200 sm:py-3">
        <div className="min-w-0 flex-1">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Ask meetings
        </p>
        <p className="mt-1 truncate text-sm font-medium text-teal-800" title={scopeLabel}>
          {scopeLabel}
        </p>
        </div>
        <button
          type="button"
          onClick={() => setRecentOpen((o) => !o)}
          aria-expanded={recentOpen}
          aria-controls="meeting-chat-recent"
          className="flex min-h-[44px] shrink-0 items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-100 sm:hidden"
        >
          Recent
          <ChevronDownIcon className={`h-4 w-4 transition-transform ${recentOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={newChat}
          disabled={isRunning}
          className="flex min-h-[44px] shrink-0 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-100 disabled:opacity-50 sm:mt-3 sm:min-h-0 sm:w-full"
        >
          <PlusIcon className="h-4 w-4" />
          New chat
        </button>
      </div>

      <nav
        id="meeting-chat-recent"
        className={`${recentOpen ? 'block' : 'hidden'} max-h-48 overflow-y-auto border-t border-slate-200 px-2 py-2 sm:block sm:max-h-none sm:flex-1 sm:border-t-0`}
        aria-label="Recent chats"
      >
        <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Recent
        </p>
        <ul className="space-y-0.5">
          {threads.map((t) => {
            const active = t.id === activeId
            return (
              <li key={t.id} className="group relative">
                <button
                  type="button"
                  onClick={() => {
                    selectThread(t.id)
                    setRecentOpen(false)
                  }}
                  className={`min-h-[44px] w-full truncate rounded-lg px-2.5 py-2 pr-10 text-left text-sm sm:min-h-0 sm:pr-8 ${
                    active
                      ? 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200'
                      : 'text-slate-700 hover:bg-white hover:text-slate-900'
                  }`}
                  title={t.title}
                >
                  {t.title}
                </button>
                <button
                  type="button"
                  aria-label={`Delete ${t.title}`}
                  onClick={(e) => {
                    e.stopPropagation()
                    deleteThread(t.id)
                  }}
                  className="absolute right-1 top-1/2 -translate-y-1/2 rounded p-2 text-slate-500 hover:bg-slate-200 hover:text-slate-700 sm:p-1 sm:text-slate-400 sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100"
                >
                  <TrashIcon className="h-3.5 w-3.5" />
                </button>
              </li>
            )
          })}
        </ul>
      </nav>

      <p className="hidden border-t border-slate-200 px-3 py-2 text-[11px] leading-snug text-slate-500 sm:block">
        Answers use meeting summaries. Quotes load transcript cues only when you ask.
      </p>
    </aside>
  )
}
