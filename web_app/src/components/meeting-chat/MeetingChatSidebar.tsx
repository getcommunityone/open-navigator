/**
 * Meeting chat thread rail (#652 / #670): New chat, scope, recent threads — right side, light.
 */
import { PlusIcon, TrashIcon } from '@heroicons/react/24/outline'
import { useMeetingChatControls } from './MeetingChatRuntime'

export function MeetingChatSidebar({ scopeLabel }: { scopeLabel: string }) {
  const { threads, activeId, newChat, selectThread, deleteThread, isRunning } =
    useMeetingChatControls()

  return (
    <aside className="flex h-full w-[min(100%,11.5rem)] shrink-0 flex-col border-l border-slate-200 bg-slate-50 text-slate-800 sm:w-44">
      <div className="border-b border-slate-200 px-3 py-3">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Ask meetings
        </p>
        <p className="mt-1 truncate text-sm font-medium text-teal-800" title={scopeLabel}>
          {scopeLabel}
        </p>
        <button
          type="button"
          onClick={newChat}
          disabled={isRunning}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm hover:bg-slate-100 disabled:opacity-50"
        >
          <PlusIcon className="h-4 w-4" />
          New chat
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-2" aria-label="Recent chats">
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
                  onClick={() => selectThread(t.id)}
                  className={`w-full truncate rounded-lg px-2.5 py-2 pr-8 text-left text-sm ${
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
                  className="absolute right-1 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 opacity-0 hover:bg-slate-200 hover:text-slate-700 group-hover:opacity-100"
                >
                  <TrashIcon className="h-3.5 w-3.5" />
                </button>
              </li>
            )
          })}
        </ul>
      </nav>

      <p className="border-t border-slate-200 px-3 py-2 text-[11px] leading-snug text-slate-500">
        Answers use meeting summaries. Quotes load transcript cues only when you ask.
      </p>
    </aside>
  )
}
