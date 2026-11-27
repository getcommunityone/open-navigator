/** True when `to` is the page the reader is on: same path, and every query value it sets already set. A link
 *  there does nothing visible, so the card says so instead of offering a button. */
export function isCurrentPage(to: string, pathname: string, search: string): boolean {
  const u = new URL(to, 'http://x')
  if (u.pathname !== pathname) return false
  const here = new URLSearchParams(search)
  for (const [k, v] of u.searchParams) if (here.get(k) !== v) return false
  return true
}
