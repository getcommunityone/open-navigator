/** The one address the site's contact links use (#860). */
export const CONTACT_EMAIL = 'johnbowyer@communityone.com'

/** A mailto link to the contact address, with an optional subject. */
export function contactMailto(subject?: string): string {
  const s = (subject ?? '').trim()
  return s ? `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(s)}` : `mailto:${CONTACT_EMAIL}`
}
