import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import DocumentViewer from './DocumentViewer'

/**
 * DocumentViewerContext — the document analogue of MeetingVideoContext.
 *
 * The hero's "Agenda" / "Minutes" chips call openDocument(...) to launch the PDF
 * in ONE centered modal popout (react-pdf inside), mirroring how "Watch
 * recording" pops open the video. One modal exists at a time; closing it unmounts
 * the viewer so the PDF.js worker + bytes are released.
 */

interface DocTarget {
  /** Real external document URL (proxied same-origin by the viewer). */
  url: string
  /** Heading label, e.g. "Agenda" or "Minutes". */
  label: string
  /** Optional caption (e.g. the document date). */
  caption?: string
  /** Optional in-app route back to the meeting this document belongs to. */
  backHref?: string
  /** Label for the back link (defaults to "Back to meeting"). */
  backLabel?: string
}

interface DocumentViewerCtx {
  openDocument: (target: DocTarget) => void
}

const Ctx = createContext<DocumentViewerCtx | null>(null)

/** Hook for triggers (chips). Returns null when no provider is mounted. */
// eslint-disable-next-line react-refresh/only-export-components
export function useDocumentViewer(): DocumentViewerCtx | null {
  return useContext(Ctx)
}

export function DocumentViewerProvider({ children }: { children: ReactNode }) {
  const [target, setTarget] = useState<DocTarget | null>(null)
  const openDocument = useCallback((t: DocTarget) => setTarget(t), [])
  const ctx = useMemo<DocumentViewerCtx>(() => ({ openDocument }), [openDocument])

  return (
    <Ctx.Provider value={ctx}>
      {children}

      {target && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 sm:p-8"
          onClick={() => setTarget(null)}
          role="dialog"
          aria-modal="true"
          aria-label={target.label}
        >
          <div className="relative w-full max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setTarget(null)}
              aria-label="Close document"
              className="absolute right-2 top-2 z-10 rounded-full bg-white/90 p-1.5 text-gray-500 shadow ring-1 ring-slate-900/5 hover:bg-white hover:text-gray-900"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
            <DocumentViewer
              url={target.url}
              label={target.label}
              caption={target.caption}
              backHref={target.backHref}
              backLabel={target.backLabel}
              onNavigateBack={() => setTarget(null)}
            />
          </div>
        </div>
      )}
    </Ctx.Provider>
  )
}
