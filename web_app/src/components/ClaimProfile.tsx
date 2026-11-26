// "Is this you?" — claim an official's profile and propose edits (#1062).
// Verified claims (sign-in email matches the official address) can propose a new
// title, biography or photo URL; any claimant can send feedback. Every submission
// is stored pending for review — nothing is published automatically or emailed.
import { useEffect, useState, type FormEvent } from 'react'
import { useAuth } from '../contexts/AuthContext'
import {
  claimErrorMessage,
  claimProfile,
  fetchMyClaim,
  proposeProfileEdit,
  type PersonClaim,
  type ProfileEditField,
} from '../api/personClaims'

const PROVIDERS: { id: string; name: string }[] = [
  { id: 'google', name: 'Google' },
  { id: 'facebook', name: 'Facebook' },
  { id: 'github', name: 'GitHub' },
]

const buttonClass =
  'min-h-[44px] rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 shadow-sm hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-600 disabled:opacity-50'
const primaryClass =
  'min-h-[44px] rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-600 disabled:opacity-50'

function EditField({
  claimId,
  field,
  label,
  multiline,
  placeholder,
  inputType = 'text',
}: {
  claimId: number
  field: ProfileEditField
  label: string
  multiline?: boolean
  placeholder?: string
  inputType?: string
}) {
  const [value, setValue] = useState('')
  const [state, setState] = useState<'idle' | 'sending' | 'sent'>('idle')
  const [error, setError] = useState<string | null>(null)
  const inputId = `claim-${field}`

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!value.trim()) return
    setState('sending')
    setError(null)
    try {
      await proposeProfileEdit(claimId, field, value.trim())
      setState('sent')
      setValue('')
    } catch (err) {
      setError(claimErrorMessage(err, 'Could not send this. Please try again.'))
      setState('idle')
    }
  }

  const inputClass =
    'w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-600'
  return (
    <form onSubmit={submit} className="space-y-2">
      <label htmlFor={inputId} className="block text-sm font-medium text-slate-800">
        {label}
      </label>
      {multiline ? (
        <textarea
          id={inputId}
          rows={4}
          maxLength={4000}
          value={value}
          placeholder={placeholder}
          onChange={(e) => {
            setValue(e.target.value)
            if (state === 'sent') setState('idle')
          }}
          className={inputClass}
        />
      ) : (
        <input
          id={inputId}
          type={inputType}
          maxLength={4000}
          value={value}
          placeholder={placeholder}
          onChange={(e) => {
            setValue(e.target.value)
            if (state === 'sent') setState('idle')
          }}
          className={inputClass}
        />
      )}
      <div className="flex items-center gap-3">
        <button type="submit" disabled={state === 'sending' || !value.trim()} className={buttonClass}>
          {state === 'sending' ? 'Sending…' : 'Send'}
        </button>
        {state === 'sent' && (
          <span role="status" className="text-sm text-teal-800">
            Sent for review
          </span>
        )}
        {error && (
          <span role="alert" className="text-sm text-red-700">
            {error}
          </span>
        )}
      </div>
    </form>
  )
}

export default function ClaimProfile({ personId }: { personId: string }) {
  const { isAuthenticated, isLoading: authLoading, login } = useAuth()
  const [claim, setClaim] = useState<PersonClaim | null>(null)
  const [loading, setLoading] = useState(false)
  const [claiming, setClaiming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isAuthenticated) {
      setClaim(null)
      return
    }
    let cancelled = false
    setLoading(true)
    fetchMyClaim(personId)
      .then((c) => {
        if (!cancelled) setClaim(c)
      })
      .catch(() => {
        if (!cancelled) setClaim(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [isAuthenticated, personId])

  const onClaim = async () => {
    setClaiming(true)
    setError(null)
    try {
      setClaim(await claimProfile(personId))
    } catch (err) {
      setError(claimErrorMessage(err, 'Could not claim this profile. Please try again.'))
    } finally {
      setClaiming(false)
    }
  }

  return (
    <section className="bg-white rounded-lg shadow-sm p-6 mt-6" aria-labelledby="claim-profile-heading">
      <h2 id="claim-profile-heading" className="text-lg font-bold text-gray-900 mb-2">
        Is this you?
      </h2>

      {authLoading || loading ? (
        <p className="text-sm text-slate-600">Loading…</p>
      ) : !isAuthenticated ? (
        <>
          <p className="text-sm text-slate-600 mb-3">
            Sign in to claim this profile. If your sign-in email is the official address on your government&apos;s
            site, you can then suggest corrections to your title, biography and photo.
          </p>
          <div className="flex flex-wrap gap-2">
            {PROVIDERS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => login(p.id, window.location.href)}
                className={buttonClass}
              >
                Continue with {p.name}
              </button>
            ))}
          </div>
        </>
      ) : !claim ? (
        <>
          <p className="text-sm text-slate-600 mb-3">
            Claim this profile to suggest corrections. We check your sign-in email against the official address we
            have on file; we never show that address.
          </p>
          <button type="button" onClick={onClaim} disabled={claiming} className={primaryClass}>
            {claiming ? 'Claiming…' : 'Claim this profile'}
          </button>
          {error && (
            <p role="alert" className="mt-2 text-sm text-red-700">
              {error}
            </p>
          )}
        </>
      ) : claim.status === 'rejected' ? (
        <p className="text-sm text-slate-700">We reviewed this claim and could not confirm it.</p>
      ) : (
        <div className="space-y-5">
          {claim.status === 'verified' ? (
            <p role="status" className="text-sm font-medium text-teal-800">
              Verified — matched your official email
            </p>
          ) : (
            <p role="status" className="text-sm text-slate-700">
              We&apos;ll review this claim and get back to you. Meanwhile you can send us feedback.
            </p>
          )}

          {claim.status === 'verified' && (
            <>
              <p className="text-sm text-slate-600">
                Suggested changes are reviewed before they appear on this page.
              </p>
              <EditField claimId={claim.person_claim_id} field="title" label="New title" />
              <EditField claimId={claim.person_claim_id} field="biography" label="New biography" multiline />
              <EditField
                claimId={claim.person_claim_id}
                field="photo_url"
                label="New photo URL (https://)"
                inputType="url"
                placeholder="https://"
              />
            </>
          )}
          <EditField
            claimId={claim.person_claim_id}
            field="feedback"
            label="Feedback"
            multiline
            placeholder="Anything wrong or missing on this page?"
          />
        </div>
      )}
    </section>
  )
}
