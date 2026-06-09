import { useEffect, useRef } from 'react'

/**
 * PersonalizeFeedModal — the gate shown when a signed-out (or not-yet-set-up)
 * visitor taps the "Close to Home" lens. It invites them to sign in and set up
 * a personalized feed. No data is fetched or fabricated here; it's purely a
 * call-to-action over the homepage.
 */
interface PersonalizeFeedModalProps {
  open: boolean
  onClose: () => void
  isAuthenticated: boolean
  /** Signed-out path: kick off OAuth. */
  onSignIn: () => void
  /** Signed-in (profile incomplete) path: go to the setup wizard. */
  onSetUp: () => void
}

export default function PersonalizeFeedModal({
  open,
  onClose,
  isAuthenticated,
  onSignIn,
  onSetUp,
}: PersonalizeFeedModalProps) {
  const primaryRef = useRef<HTMLButtonElement>(null)

  // ESC closes; focus the primary CTA when the dialog opens.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    // Defer focus a tick so the element is mounted/painted.
    const t = window.setTimeout(() => primaryRef.current?.focus(), 0)
    return () => {
      document.removeEventListener('keydown', onKey)
      window.clearTimeout(t)
    }
  }, [open, onClose])

  if (!open) return null

  const primaryLabel = isAuthenticated ? 'Set up my feed' : 'Sign in & set it up'
  const onPrimary = isAuthenticated ? onSetUp : onSignIn

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4"
      style={{ fontFamily: "'DM Sans', sans-serif" }}
    >
      {/* Dim backdrop — click to dismiss */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-[1px]"
        aria-hidden="true"
        onClick={onClose}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="personalize-feed-title"
        className="relative z-10 w-full max-w-md rounded-2xl border border-[#e1ebe7] bg-white p-7 shadow-[0_20px_60px_rgba(20,40,35,0.25)]"
      >
        <div
          className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl text-[28px]"
          style={{ background: 'rgba(26,107,107,0.10)' }}
          aria-hidden
        >
          🏠
        </div>

        <h2
          id="personalize-feed-title"
          className="mb-2 text-[22px] font-semibold leading-tight tracking-tight text-[#0f2b2b]"
          style={{ fontFamily: "'Newsreader', Georgia, serif" }}
        >
          Close to Home
        </h2>

        <p className="mb-6 text-[14.5px] leading-relaxed text-[#56635e]">
          See civic activity near you, on the issues you care about. Sign in and tell us a little
          about your area to personalize your feed.
        </p>

        <div className="flex flex-col gap-2.5">
          <button
            ref={primaryRef}
            type="button"
            onClick={onPrimary}
            className="w-full rounded-xl bg-[#1a6b6b] px-4 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-[#155757] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a6b6b]/50"
          >
            {primaryLabel}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-xl px-4 py-2.5 text-[14px] font-semibold text-[#56635e] transition-colors hover:text-[#0f2b2b]"
          >
            Not now
          </button>
        </div>
      </div>
    </div>
  )
}
