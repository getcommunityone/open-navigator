/**
 * assistant-ui ExternalStore runtime → POST /api/chat/meetings (#630).
 * One FastAPI call per user message; no agent SDK on the backend.
 */
import { useCallback, useState, type ReactNode } from 'react'
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from '@assistant-ui/react'
import { apiBaseUrl } from '../../lib/api'
import { withSpan } from '../../instrumentation'

export type MeetingChatCitation = {
  title: string
  place: string
  date: string
  url: string
  event_meeting_id?: number | null
  video_id?: string | null
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: MeetingChatCitation[]
  found?: boolean
}

type ChatApiResponse = {
  answer: string
  citations: MeetingChatCitation[]
  found: boolean
  mode: string
}

export type MeetingChatScope = {
  state?: string
  city?: string
  county_fips?: string
}

function convertMessage(message: ChatMessage): ThreadMessageLike {
  return {
    id: message.id,
    role: message.role,
    content: [{ type: 'text', text: message.content }],
  }
}

export function MeetingChatRuntimeProvider({
  scope,
  children,
}: {
  scope: MeetingChatScope
  children: ReactNode
}) {
  const [isRunning, setIsRunning] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Ask about local meetings in this scope. I answer from meeting summaries and cite the meetings I used. Ask for a quote when you need transcript detail.',
      citations: [],
      found: true,
    },
  ])

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const part = message.content[0]
      if (!part || part.type !== 'text') {
        throw new Error('Only text messages are supported')
      }
      const input = part.text.trim()
      if (!input) return

      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: 'user', content: input },
      ])
      setIsRunning(true)
      try {
        const data = await withSpan('chat.meetings.request', async () => {
          const controller = new AbortController()
          const timer = window.setTimeout(() => controller.abort(), 60_000)
          try {
            const res = await fetch(`${apiBaseUrl}/chat/meetings`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              signal: controller.signal,
              body: JSON.stringify({
                question: input,
                state: scope.state || undefined,
                city: scope.city || undefined,
                county_fips: scope.county_fips || undefined,
              }),
            })
            const body = (await res.json()) as ChatApiResponse & { detail?: string }
            if (!res.ok) {
              throw { response: { status: res.status, data: body } }
            }
            return body
          } finally {
            window.clearTimeout(timer)
          }
        })
        const cites = data.citations ?? []
        const citeBlock =
          cites.length > 0
            ? '\n\nSources:\n' +
              cites
                .map((c) => {
                  const where = [c.place, c.date].filter(Boolean).join(' · ')
                  return `• ${c.title}${where ? ` (${where})` : ''} — ${c.url}`
                })
                .join('\n')
            : ''
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `${data.answer}${citeBlock}`,
            citations: cites,
            found: data.found,
          },
        ])
      } catch (err: unknown) {
        const status = (
          err as { response?: { status?: number; data?: { detail?: string } } }
        )?.response
        const detail =
          status?.data?.detail ||
          (status?.status === 429
            ? 'Rate limit reached. Please wait a moment.'
            : status?.status === 503
              ? 'Daily chat budget reached. Try again tomorrow.'
              : 'Something went wrong answering that. Please try again.')
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: String(detail),
            citations: [],
            found: false,
          },
        ])
      } finally {
        setIsRunning(false)
      }
    },
    [scope.state, scope.city, scope.county_fips],
  )

  const runtime = useExternalStoreRuntime({
    isRunning,
    messages,
    convertMessage,
    onNew,
  })

  return <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>
}
