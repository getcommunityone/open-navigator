import { Popover } from '@headlessui/react'
import { InformationCircleIcon, XMarkIcon } from '@heroicons/react/24/outline'

const DEFAULT_BTN =
  'rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400'

export type InfoHelpTriggerProps = {
  help: string
  /** Short topic for the control (used in ``aria-label`` only). */
  topic: string
  /** Panel alignment under the trigger. */
  align?: 'left' | 'right'
  buttonClassName?: string
  /**
   * Where the panel opens on a narrow screen (≤ 760px). ``anchored`` (default)
   * keeps it under the trigger, as on desktop. ``top`` docks it as a small
   * popover near the top of the window, so help opened from a bottom sheet
   * does not stack over the sheet's own content (#1238). Desktop is unchanged.
   */
  mobilePlacement?: 'anchored' | 'top'
}

const MOBILE_TOP =
  'max-[760px]:fixed max-[760px]:top-20 max-[760px]:left-4 max-[760px]:right-4 max-[760px]:mt-0 max-[760px]:w-auto'

/**
 * Census map / charts: replaces ``title=`` on info icons — native tooltips are hover-only
 * and unreliable on touch; this opens a readable panel on click or tap (and supports
 * keyboard). It never opens on hover or focus. The panel closes with its close button,
 * Escape, or a tap/click outside it.
 */
export function InfoHelpTrigger({
  help,
  topic,
  align = 'left',
  buttonClassName = DEFAULT_BTN,
  mobilePlacement = 'anchored',
}: InfoHelpTriggerProps) {
  const panelAlign = align === 'right' ? 'right-0' : 'left-0'
  const mobile = mobilePlacement === 'top' ? MOBILE_TOP : ''
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
        className={`absolute ${panelAlign} z-[300] mt-1 w-[min(calc(100vw-2rem),24rem)] max-h-72 overflow-y-auto rounded-lg border border-slate-200 bg-white p-3 pr-8 text-left text-xs leading-relaxed text-slate-700 shadow-xl ring-1 ring-black/5 max-[760px]:max-h-[40vh] ${mobile}`}
      >
        {({ close }) => (
          <>
            <button
              type="button"
              onClick={() => close()}
              data-testid="info-help-close"
              aria-label="Close"
              className="absolute right-1.5 top-1.5 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
            >
              <XMarkIcon className="h-4 w-4" aria-hidden />
            </button>
            <p className="whitespace-pre-wrap">{help}</p>
          </>
        )}
      </Popover.Panel>
    </Popover>
  )
}
