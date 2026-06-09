import { useState, useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { withSpan } from '../instrumentation'
import {
  LifebuoyIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline'

// Vite proxy handles dev routing; matches the app-wide convention (see AuthContext).
const API_URL = '/api'

const CATEGORIES = [
  { value: 'feedback', label: 'Feedback' },
  { value: 'bug', label: 'Bug report' },
  { value: 'feature', label: 'Feature request' },
  { value: 'question', label: 'Question' },
] as const

type CategoryValue = (typeof CATEGORIES)[number]['value']

const VALID_CATEGORIES = CATEGORIES.map((c) => c.value) as readonly string[]

// Backend bounds (api/routes/contact.py ContactRequest) — mirror client-side.
const NAME_MAX = 100
const SUBJECT_MAX = 200
const MESSAGE_MIN = 10
const MESSAGE_MAX = 5000

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

interface ContactSuccess {
  success: boolean
  message: string
  issue_url?: string | null
}

/** Pull the GitHub issue number out of an issue URL, if present. */
function issueNumberFromUrl(url?: string | null): string | null {
  if (!url) return null
  const m = url.match(/\/issues\/(\d+)/)
  return m ? m[1] : null
}

export default function Support() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()

  const prefillSubject = searchParams.get('subject') ?? ''
  const prefillCategoryRaw = searchParams.get('category') ?? ''
  const prefillPath = searchParams.get('path') ?? ''

  const prefillCategory: CategoryValue = VALID_CATEGORIES.includes(prefillCategoryRaw)
    ? (prefillCategoryRaw as CategoryValue)
    : 'feedback'

  const initialMessage = useMemo(
    () => (prefillPath ? `Page/action: ${prefillPath}\n\n` : ''),
    [prefillPath],
  )

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [category, setCategory] = useState<CategoryValue>(prefillCategory)
  const [subject, setSubject] = useState(prefillSubject)
  const [message, setMessage] = useState(initialMessage)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [success, setSuccess] = useState<ContactSuccess | null>(null)
  const [touched, setTouched] = useState(false)

  // Prefill name/email from the logged-in user when available. Only fill empty
  // fields so we don't clobber what the user has typed.
  useEffect(() => {
    if (!user) return
    setName((prev) => prev || user.full_name || user.username || '')
    setEmail((prev) => prev || user.email || '')
  }, [user])

  const trimmedName = name.trim()
  const trimmedEmail = email.trim()
  const trimmedSubject = subject.trim()
  const trimmedMessage = message.trim()

  const fieldErrors: Record<string, string> = {}
  if (!trimmedName) fieldErrors.name = 'Name is required'
  else if (trimmedName.length > NAME_MAX)
    fieldErrors.name = `Name must be ${NAME_MAX} characters or fewer`
  if (!trimmedEmail) fieldErrors.email = 'Email is required'
  else if (!EMAIL_RE.test(trimmedEmail)) fieldErrors.email = 'Enter a valid email address'
  if (!trimmedSubject) fieldErrors.subject = 'Subject is required'
  else if (trimmedSubject.length > SUBJECT_MAX)
    fieldErrors.subject = `Subject must be ${SUBJECT_MAX} characters or fewer`
  if (trimmedMessage.length < MESSAGE_MIN)
    fieldErrors.message = `Message must be at least ${MESSAGE_MIN} characters`
  else if (trimmedMessage.length > MESSAGE_MAX)
    fieldErrors.message = `Message must be ${MESSAGE_MAX} characters or fewer`

  const isValid = Object.keys(fieldErrors).length === 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setTouched(true)
    setSubmitError(null)
    if (!isValid || isSubmitting) return

    setIsSubmitting(true)
    try {
      await withSpan(
        'contact.submit',
        async () => {
          const response = await fetch(`${API_URL}/contact/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              name: trimmedName,
              email: trimmedEmail,
              subject: trimmedSubject,
              message: trimmedMessage,
              category,
            }),
          })

          if (response.status === 201) {
            const data: ContactSuccess = await response.json()
            setSuccess(data)
            return
          }

          // Surface the backend's `detail` if present, else a friendly fallback.
          let detail = 'Something went wrong while submitting your request. Please try again.'
          try {
            const body = await response.json()
            if (body && typeof body.detail === 'string') detail = body.detail
          } catch {
            // non-JSON error body — keep the friendly fallback
          }
          setSubmitError(detail)
          throw new Error(`contact submit failed: ${response.status}`)
        },
        { 'contact.category': category },
      )
    } catch (err) {
      // Network-level failure (no response). Don't overwrite a parsed detail.
      if (!submitError) {
        setSubmitError(
          'We could not reach the server. Please check your connection and try again.',
        )
      }
      console.error('Contact form submission failed:', err)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Success state
  if (success) {
    const issueNumber = issueNumberFromUrl(success.issue_url)
    return (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <CheckCircleIcon className="h-14 w-14 text-green-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold mb-2" style={{ color: '#354F52' }}>
            Thanks — we've got it
          </h1>
          <p className="text-gray-600 mb-6">
            {issueNumber ? (
              <>
                We've logged your request as ticket{' '}
                <span className="font-semibold">#{issueNumber}</span>.
              </>
            ) : (
              <>We've logged your request.</>
            )}{' '}
            We'll follow up at <span className="font-medium">{trimmedEmail}</span>.
          </p>
          {success.issue_url && (
            <a
              href={success.issue_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block px-6 py-2.5 text-white rounded-lg transition-colors font-medium"
              style={{ backgroundColor: '#354F52' }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#2e4346')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#354F52')}
            >
              View ticket on GitHub
            </a>
          )}
          <div className="mt-6">
            <button
              type="button"
              onClick={() => {
                setSuccess(null)
                setSubject('')
                setMessage(initialMessage)
                setTouched(false)
              }}
              className="text-sm text-primary-600 hover:text-primary-700 hover:underline font-medium"
            >
              Submit another request
            </button>
          </div>
        </div>
      </div>
    )
  }

  const showError = (field: string) => touched && fieldErrors[field]

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold mb-2" style={{ color: '#354F52' }}>
        Contact support
      </h1>
      <p className="text-gray-600 mb-8">
        Found a bug, have a feature idea, or just want to share feedback? Send us a note
        and we'll get back to you.
      </p>

      <div className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-200 px-6 py-4">
          <div className="flex items-center gap-2">
            <LifebuoyIcon className="h-6 w-6 text-gray-600" />
            <h2 className="text-xl font-semibold text-gray-900">Send a message</h2>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4" noValidate>
          <div className="space-y-4">
            {/* Name */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="name"
                value={name}
                maxLength={NAME_MAX}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                  showError('name') ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {showError('name') && (
                <p className="mt-1 text-sm text-red-600">{fieldErrors.name}</p>
              )}
            </div>

            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                Email <span className="text-red-500">*</span>
              </label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                  showError('email') ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {showError('email') && (
                <p className="mt-1 text-sm text-red-600">{fieldErrors.email}</p>
              )}
            </div>

            {/* Category */}
            <div>
              <label htmlFor="category" className="block text-sm font-medium text-gray-700 mb-1">
                Category
              </label>
              <select
                id="category"
                value={category}
                onChange={(e) => setCategory(e.target.value as CategoryValue)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Subject */}
            <div>
              <label htmlFor="subject" className="block text-sm font-medium text-gray-700 mb-1">
                Subject <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="subject"
                value={subject}
                maxLength={SUBJECT_MAX}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="A short summary"
                className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                  showError('subject') ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {showError('subject') && (
                <p className="mt-1 text-sm text-red-600">{fieldErrors.subject}</p>
              )}
            </div>

            {/* Message */}
            <div>
              <label htmlFor="message" className="block text-sm font-medium text-gray-700 mb-1">
                Message <span className="text-red-500">*</span>
              </label>
              <textarea
                id="message"
                value={message}
                maxLength={MESSAGE_MAX}
                onChange={(e) => setMessage(e.target.value)}
                rows={7}
                placeholder="Tell us what's going on (at least 10 characters)…"
                className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 resize-y ${
                  showError('message') ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              <div className="mt-1 flex items-center justify-between">
                {showError('message') ? (
                  <p className="text-sm text-red-600">{fieldErrors.message}</p>
                ) : (
                  <span />
                )}
                <span className="text-xs text-gray-400">
                  {trimmedMessage.length}/{MESSAGE_MAX}
                </span>
              </div>
            </div>
          </div>

          {/* Submit-time error */}
          {submitError && (
            <div className="mt-4 p-4 rounded-lg flex items-start gap-2 bg-red-50 text-red-800">
              <ExclamationCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
              <span>{submitError}</span>
            </div>
          )}

          {/* Submit */}
          <div className="mt-6">
            <button
              type="submit"
              disabled={isSubmitting || (touched && !isValid)}
              className="w-full sm:w-auto px-6 py-2.5 text-white rounded-lg transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ backgroundColor: '#354F52' }}
              onMouseEnter={(e) =>
                !isSubmitting && (e.currentTarget.style.backgroundColor = '#2e4346')
              }
              onMouseLeave={(e) =>
                !isSubmitting && (e.currentTarget.style.backgroundColor = '#354F52')
              }
            >
              {isSubmitting ? 'Sending…' : 'Send message'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
