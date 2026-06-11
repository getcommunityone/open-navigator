import { useEffect, useRef, useState } from 'react'

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
  /** Signed-out path: kick off OAuth with the chosen provider. */
  onSignIn: (provider: string) => void
  /** Signed-in (profile incomplete) path: go to the setup wizard. */
  onSetUp: () => void
}

/** OAuth providers offered in the sign-in step (mirrors the header dropdown). */
const PROVIDERS: { id: string; label: string; icon: JSX.Element }[] = [
  {
    id: 'google',
    label: 'Google',
    icon: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" preserveAspectRatio="xMidYMid meet">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
      </svg>
    ),
  },
  {
    id: 'facebook',
    label: 'Facebook',
    icon: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="#1877F2">
        <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
      </svg>
    ),
  },
  {
    id: 'github',
    label: 'GitHub',
    icon: (
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="#181717">
        <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
      </svg>
    ),
  },
  {
    id: 'huggingface',
    label: 'HuggingFace',
    icon: <span className="text-2xl leading-none">🤗</span>,
  },
]

export default function PersonalizeFeedModal({
  open,
  onClose,
  isAuthenticated,
  onSignIn,
  onSetUp,
}: PersonalizeFeedModalProps) {
  const primaryRef = useRef<HTMLButtonElement>(null)
  // Signed-out two-step: the primary CTA reveals the OAuth provider choices.
  const [showProviders, setShowProviders] = useState(false)

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

  // Reset to the intro step whenever the dialog re-opens.
  useEffect(() => {
    if (!open) setShowProviders(false)
  }, [open])

  if (!open) return null

  const primaryLabel = isAuthenticated ? 'Set up my feed' : 'Sign in & set it up'
  const onPrimary = isAuthenticated ? onSetUp : () => setShowProviders(true)

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
          {showProviders
            ? 'Choose how you’d like to sign in. We’ll bring you right back to set up your feed.'
            : 'See civic activity near you, on the issues you care about. Sign in and tell us a little about your area to personalize your feed.'}
        </p>

        {showProviders ? (
          <div className="flex flex-col gap-2">
            {PROVIDERS.map((p, i) => (
              <button
                key={p.id}
                ref={i === 0 ? primaryRef : undefined}
                type="button"
                onClick={() => onSignIn(p.id)}
                className="flex w-full items-center gap-3 rounded-xl border border-[#e1ebe7] px-4 py-3 text-[15px] font-semibold text-[#0f2b2b] transition-colors hover:bg-[#f3f7f5] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#1a6b6b]/50"
              >
                <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center">
                  {p.icon}
                </span>
                <span>Continue with {p.label}</span>
              </button>
            ))}
            <button
              type="button"
              onClick={onClose}
              className="mt-1 w-full rounded-xl px-4 py-2.5 text-[14px] font-semibold text-[#56635e] transition-colors hover:text-[#0f2b2b]"
            >
              Not now
            </button>
          </div>
        ) : (
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
        )}
      </div>
    </div>
  )
}
