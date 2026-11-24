/**
 * What to tell the reader when a lazily loaded page fails to load (#856).
 *
 * In development the usual cause is a dependency added by a pull that has not been installed yet,
 * so the message says how to fix that. The error's own text is shown as given, never reworded.
 */
export function lazyRouteFailureMessage(name: string, error: unknown): { title: string; detail: string; hint: string } {
  const raw = error instanceof Error ? error.message : typeof error === 'string' ? error : ''
  return {
    title: `${name} could not be loaded`,
    detail: raw.trim() || 'The page failed to load. No further detail was reported.',
    hint: 'The rest of the site still works. If you run the site yourself, run "npm install" in web_app, then reload.',
  }
}
