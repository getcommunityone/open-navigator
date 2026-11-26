// API client for claiming an official's profile (#1062).
//   POST /api/people/claim                          {person_id}
//   GET  /api/people/claim?person_id=...
//   POST /api/people/claim/{person_claim_id}/edits  {field, new_value}
// All three need a signed-in user; the shared client adds the Authorization header.
// Nothing here is published automatically: every edit is stored pending for review.
import api from '../lib/api'
import { withSpan } from '../instrumentation'

export type PersonClaimStatus = 'pending' | 'verified' | 'rejected'
export type ProfileEditField = 'title' | 'biography' | 'photo_url' | 'feedback'

export interface PersonClaim {
  person_claim_id: number
  person_id: string
  status: PersonClaimStatus
  /** 'official_email' when the sign-in email matched the official address. */
  verified_via: string | null
  created_at: string | null
  updated_at: string | null
}

export interface ProfileEdit {
  person_profile_edit_id: number
  person_claim_id: number
  field: ProfileEditField
  new_value: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string | null
}

/** Official ids are OCD membership ids; only those can be claimed. */
export function isOfficialId(id: string | undefined | null): boolean {
  return !!id && id.startsWith('ocd-membership/')
}

export async function fetchMyClaim(personId: string): Promise<PersonClaim | null> {
  const res = await api.get<PersonClaim | null>('/people/claim', { params: { person_id: personId } })
  return res.data ?? null
}

export async function claimProfile(personId: string): Promise<PersonClaim> {
  return withSpan('person-claim.claim', async (span) => {
    const res = await api.post<PersonClaim>('/people/claim', { person_id: personId })
    span.setAttribute('person_claim.status', res.data.status)
    return res.data
  })
}

export async function proposeProfileEdit(
  personClaimId: number,
  field: ProfileEditField,
  newValue: string,
): Promise<ProfileEdit> {
  return withSpan(
    'person-claim.edit',
    async () => {
      const res = await api.post<ProfileEdit>(`/people/claim/${personClaimId}/edits`, {
        field,
        new_value: newValue,
      })
      return res.data
    },
    { 'person_claim.field': field },
  )
}

/** Pull a readable message out of the client's thrown error shape. */
export function claimErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const msg = (detail[0] as { msg?: unknown })?.msg
    if (typeof msg === 'string') return msg
  }
  return fallback
}
