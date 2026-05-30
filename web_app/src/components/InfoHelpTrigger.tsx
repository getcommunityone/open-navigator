import { Popover } from '@headlessui/react'
import { InformationCircleIcon } from '@heroicons/react/24/outline'

const DEFAULT_BTN =
  'rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400'

export type InfoHelpTriggerProps = {
  help: string
  /** Short topic for the control (used in ``aria-label`` only). */
  topic: string
  /** Panel alignment under the trigger. */
  align?: 'left' | 'right'
  buttonClassName?: string
}

/**
 * Census map / charts: replaces ``title=`` on info icons — native tooltips are hover-only
 * and unreliable on touch; this opens a readable panel on click (and supports keyboard).
 */
export function InfoHelpTrigger({
  help,
  topic,
  align = 'left',
  buttonClassName = DEFAULT_BTN,
}: InfoHelpTriggerProps) {
  const panelAlign = align === 'right' ? 'right-0' : 'left-0'
  return (
    <Popover className="relative inline-flex align-middle">
      <Popover.Button
        type="button"
        className={buttonClassName}
        aria-label={`${topic}: more information`}
      >
        <InformationCircleIcon className="h-3.5 w-3.5" aria-hidden />
      </Popover.Button>
      <Popover.Panel
        className={`absolute ${panelAlign} z-[300] mt-1 w-[min(calc(100vw-2rem),24rem)] max-h-72 overflow-y-auto rounded-lg border border-slate-200 bg-white p-3 text-left text-xs leading-relaxed text-slate-700 shadow-xl ring-1 ring-black/5`}
      >
        <p className="whitespace-pre-wrap">{help}</p>
      </Popover.Panel>
    </Popover>
  )
}
