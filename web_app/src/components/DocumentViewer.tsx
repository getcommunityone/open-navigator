import { useEffect, useMemo, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import {
  DocumentTextIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline'
import { apiBaseUrl } from '../lib/api'

/**
 * Inline PDF viewer for meeting agenda/minutes — the document analogue of
 * MeetingPlayer's embedded recording. Renders one page at a time with prev/next
 * paging, sized to the container.
 *
 * Government PDF hosts rarely send CORS headers, so the browser can't fetch the
 * file directly; we load it through the same-origin API proxy
 * (/document/proxy?url=…), which only serves URLs already in the warehouse. When
 * a document can't be rendered (HTML "PDF", auth wall, fetch failure) we fall
 * back to an "Open original" link rather than show a broken frame.
 */

// Bundled pdf.js worker; Vite resolves this URL at build time (no CDN dependency).
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

// Stable identity so <Document> doesn't reload on every render (react-pdf warns
// when the `options` prop changes reference).
const PDF_OPTIONS = {
  cMapUrl: 'https://unpkg.com/pdfjs-dist@4.8.69/cmaps/',
  cMapPacked: true,
}

interface DocumentViewerProps {
  /** The real external document URL (proxied for same-origin fetch). */
  url: string
  /** Heading label, e.g. "Agenda" or "Minutes". */
  label: string
  /** Optional caption under the heading (e.g. the document date). */
  caption?: string
}

export default function DocumentViewer({ url, label, caption }: DocumentViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [numPages, setNumPages] = useState(0)
  const [pageNumber, setPageNumber] = useState(1)
  const [width, setWidth] = useState<number>()
  const [failed, setFailed] = useState(false)

  // Render the page at the container's width so it scales on resize/mobile.
  useEffect(() => {
    const el = containerRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const update = () => setWidth(el.clientWidth)
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Same-origin proxy URL; the proxy validates `url` against the warehouse.
  const fileUrl = useMemo(
    () => `${apiBaseUrl}/document/proxy?url=${encodeURIComponent(url)}`,
    [url],
  )

  const goPrev = () => setPageNumber((p) => Math.max(1, p - 1))
  const goNext = () => setPageNumber((p) => Math.min(numPages || 1, p + 1))

  return (
    <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-bold text-gray-900">
          <DocumentTextIcon className="h-5 w-5 text-[#1d6b5f]" />
          {label}
          {caption && <span className="text-sm font-normal text-gray-400">{caption}</span>}
        </h2>
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex shrink-0 items-center gap-1.5 text-sm font-medium text-[#1d6b5f] hover:text-[#155448]"
        >
          <ArrowTopRightOnSquareIcon className="h-4 w-4" />
          Open original
        </a>
      </div>

      <div ref={containerRef} className="overflow-hidden rounded-lg bg-gray-100">
        {failed ? (
          <div className="flex flex-col items-center gap-2 px-4 py-12 text-center text-sm text-gray-500">
            <DocumentTextIcon className="h-8 w-8 text-gray-300" />
            <p>This document can’t be previewed here.</p>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 font-medium text-[#1d6b5f] hover:underline"
            >
              <ArrowTopRightOnSquareIcon className="h-4 w-4" />
              Open the original document →
            </a>
          </div>
        ) : (
          <Document
            file={fileUrl}
            options={PDF_OPTIONS}
            onLoadSuccess={({ numPages }) => {
              setNumPages(numPages)
              setPageNumber(1)
            }}
            onLoadError={() => setFailed(true)}
            loading={<div className="px-4 py-12 text-center text-sm text-gray-500">Loading document…</div>}
            error={<div className="px-4 py-12 text-center text-sm text-gray-500">Couldn’t load this document.</div>}
            className="flex justify-center"
          >
            <Page
              pageNumber={pageNumber}
              width={width}
              renderAnnotationLayer
              renderTextLayer
            />
          </Document>
        )}
      </div>

      {/* Page navigation — only meaningful for multi-page documents. */}
      {!failed && numPages > 1 && (
        <div className="mt-3 flex items-center justify-center gap-4 text-sm text-gray-600">
          <button
            onClick={goPrev}
            disabled={pageNumber <= 1}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 font-medium transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ChevronLeftIcon className="h-4 w-4" />
            Prev
          </button>
          <span className="tabular-nums">
            Page {pageNumber} of {numPages}
          </span>
          <button
            onClick={goNext}
            disabled={pageNumber >= numPages}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 font-medium transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Next
            <ChevronRightIcon className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  )
}
