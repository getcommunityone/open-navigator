/** The one address the site's contact links use (#860). */
export const CONTACT_EMAIL = 'johnbowyer@communityone.com'

/** A mailto link to the contact address, with an optional subject. */
export function contactMailto(subject?: string): string {
  const s = (subject ?? '').trim()
  return s ? `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(s)}` : `mailto:${CONTACT_EMAIL}`
}

/**
 * Where closing the chat panel goes (#879): back one page when the visitor arrived from inside the app, or the
 * home page when the chat was the first page opened. React Router gives the first location the key `default`.
 */
export function closeChatTarget(historyKey: string): -1 | '/' {
  return historyKey && historyKey !== 'default' ? -1 : '/'
}
