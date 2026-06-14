import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import {
  DocumentTextIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ArrowTopRightOnSquareIcon,
  ArrowLeftIcon,
} from '@heroicons/react/24/outline'
import { apiBaseUrl } from '../lib/api'

/**
 * Inline document viewer for meeting agenda/minutes — the document analogue of
 * MeetingPlayer's embedded recording. PDFs render one page at a time with
 * prev/next paging, sized to the container.
 *
 * Government document hosts rarely send CORS headers, so the browser can't fetch
 * the file directly; we load it through the same-origin API proxy
 * (/document/proxy?url=…), which only serves URLs already in the warehouse.
 *
 * Not every "minutes"/"agenda" link is a PDF — some portals serve HTML pages or
 * Word/Office files. We fetch the bytes ONCE, sniff the real type (content-type +
 * %PDF magic), and only hand actual PDFs to react-pdf. Non-PDF documents are NOT
 * forced through the PDF renderer (which would just fail) — they show a typed
 * "open the original" card instead. Any fetch/render failure also falls back to
 * that card rather than a broken frame.
 */

// Map a content-type to a human noun for the non-PDF fallback card.
function describeDocType(contentType: string): string {
  const ct = contentType.toLowerCase()
  if (ct.includes('html')) return 'web page'
  if (ct.includes('msword') || ct.includes('wordprocessing')) return 'Word document'
  if (ct.includes('spreadsheet') || ct.includes('ms-excel')) return 'spreadsheet'
  if (ct.includes('presentation') || ct.includes('powerpoint')) return 'slideshow'
  if (ct.includes('rtf')) return 'rich-text document'
  if (ct.includes('plain')) return 'text file'
  return 'document'
}

// The first bytes of a PDF are always the ASCII magic "%PDF".
function looksLikePdf(bytes: Uint8Array): boolean {
  return bytes[0] === 0x25 && bytes[1] === 0x50 && bytes[2] === 0x44 && bytes[3] === 0x46
}

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
  /** Optional in-app route back to the meeting this document belongs to. */
  backHref?: string
  /** Label for the back link (defaults to "Back to meeting"). */
  backLabel?: string
  /** Called when the back link is followed, so the host modal can close. */
  onNavigateBack?: () => void
}

type DocKind = 'loading' | 'pdf' | 'other' | 'failed'

export default function DocumentViewer({
  url,
  label,
  caption,
  backHref,
  backLabel = 'Back to meeting',
  onNavigateBack,
}: DocumentViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [numPages, setNumPages] = useState(0)
  const [pageNumber, setPageNumber] = useState(1)
  const [width, setWidth] = useState<number>()
  const [kind, setKind] = useState<DocKind>('loading')
  const [pdfData, setPdfData] = useState<Uint8Array | null>(null)
  const [docNoun, setDocNoun] = useState('document')

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

  // Fetch the bytes once and decide how to render. PDFs go to react-pdf; anything
  // else (HTML page, Word/Office file, fetch failure) shows the typed fallback
  // card — we never feed a non-PDF to the PDF renderer.
  useEffect(() => {
    let cancelled = false
    setKind('loading')
    setPdfData(null)
    fetch(fileUrl)
      .then(async (resp) => {
        if (!resp.ok) throw new Error(`proxy returned ${resp.status}`)
        const contentType = resp.headers.get('content-type') ?? ''
        const bytes = new Uint8Array(await resp.arrayBuffer())
        if (cancelled) return
        if (contentType.toLowerCase().includes('pdf') || looksLikePdf(bytes)) {
          setPdfData(bytes)
          setKind('pdf')
        } else {
          setDocNoun(describeDocType(contentType))
          setKind('other')
        }
      })
      .catch(() => {
        if (!cancelled) setKind('failed')
      })
    return () => {
      cancelled = true
    }
  }, [fileUrl])

  // Stable identity for react-pdf's `file` prop. pdf.js transfers (detaches) the
  // buffer to its worker on load, so this must NOT change reference per render or
  // it would reload from a detached buffer.
  const pdfFile = useMemo(() => (pdfData ? { data: pdfData } : null), [pdfData])

  const goPrev = () => setPageNumber((p) => Math.max(1, p - 1))
  const goNext = () => setPageNumber((p) => Math.min(numPages || 1, p + 1))

  return (
    <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
      {backHref && (
        <Link
          to={backHref}
          onClick={onNavigateBack}
          className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-gray-700"
        >
          <ArrowLeftIcon className="h-4 w-4" />
          {backLabel}
        </Link>
      )}
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
        {kind === 'loading' && (
          <div className="px-4 py-12 text-center text-sm text-gray-500">Loading document…</div>
        )}

        {(kind === 'failed' || kind === 'other') && (
          <div className="flex flex-col items-center gap-2 px-4 py-12 text-center text-sm text-gray-500">
            <DocumentTextIcon className="h-8 w-8 text-gray-300" />
            <p>
              {kind === 'other'
                ? `This ${docNoun} can’t be previewed here.`
                : 'This document can’t be previewed here.'}
            </p>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 font-medium text-[#1d6b5f] hover:underline"
            >
              <ArrowTopRightOnSquareIcon className="h-4 w-4" />
              Open the original {kind === 'other' ? docNoun : 'document'} →
            </a>
          </div>
        )}

        {kind === 'pdf' && pdfFile && (
          <Document
            file={pdfFile}
            options={PDF_OPTIONS}
            onLoadSuccess={({ numPages }) => {
              setNumPages(numPages)
              setPageNumber(1)
            }}
            onLoadError={() => setKind('failed')}
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
      {kind === 'pdf' && numPages > 1 && (
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
