import { apiErrorMessage } from './apiErrorMessage'

export type ChatErrorKind = 'server' | 'timeout' | 'offline'

export interface ChatError {
  text: string
  kind: ChatErrorKind
}

/** Where to turn when the chat cannot answer; the contact control sits at the top of the chat panel. */
const HELP = ' If this keeps happening, use "Contact us" at the top of this panel.'

/**
 * What to tell the visitor when a chat request fails (#916). The server's own reason is shown when it sent one
 * (FastAPI's `detail`, or this API's `message`); a timeout and a lost connection each get their own words, because
 * "try again" means something different for each. Never invents a reason.
 */
export function chatErrorMessage(err: unknown): ChatError {
  const e = err as { name?: string; response?: { status?: number; data?: unknown } } | null
  if (e?.name === 'AbortError') {
    return { kind: 'timeout', text: 'That took longer than a minute, so the request was stopped. Please try again.' + HELP }
  }
  const status = e?.response?.status
  if (typeof status === 'number') {
    const said = apiErrorMessage(e?.response?.data, status)
    const text = said.startsWith('HTTP ')
      ? status === 429
        ? 'Too many questions in a short time. Please wait a moment and try again.'
        : `The chat could not answer (error ${status}).`
      : said
    return { kind: 'server', text: text + HELP }
  }
  return {
    kind: 'offline',
    text: 'The chat could not be reached. Check your connection and try again.' + HELP,
  }
}
