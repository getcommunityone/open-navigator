import { isStaleChunkError } from './staleDeploy'

/**
 * What to tell the reader when a lazily loaded page fails to load (#856, #936).
 *
 * On the public site the usual cause is a deploy since the tab was opened: the page's files were
 * replaced, so a reload fixes it (staleDeploy.ts tries one automatically). In development the
 * usual cause is a dependency added by a pull that has not been installed yet. The error's own
 * text is shown as given, never reworded.
 */
export function lazyRouteFailureMessage(
  name: string,
  error: unknown,
  opts: { dev?: boolean; online?: boolean } = {},
): { title: string; detail: string; hint: string } {
  const dev = opts.dev ?? import.meta.env.DEV
  const online = opts.online ?? (typeof navigator === 'undefined' || navigator.onLine !== false)
  const raw = error instanceof Error ? error.message : typeof error === 'string' ? error : ''
  let hint = 'The rest of the site still works. Reload to try again.'
  if (dev) {
    hint = 'The rest of the site still works. If you run the site yourself, run "npm install" in web_app, then reload.'
  } else if (!online) {
    hint = 'You appear to be offline. Reconnect, then reload. The rest of the site still works.'
  } else if (isStaleChunkError(error)) {
    hint = 'This site was updated since this page was opened. Reload to get the latest version. The rest of the site still works.'
  }
  return {
    title: `${name} could not be loaded`,
    detail: raw.trim() || 'The page failed to load. No further detail was reported.',
    hint,
  }
}
