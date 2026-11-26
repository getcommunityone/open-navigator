/**
 * assistant-ui ExternalStore runtime → POST /api/chat/meetings (#630 / #652).
 * One FastAPI call per user message; local thread list in the chat sidebar.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike,
} from '@assistant-ui/react'
import { apiBaseUrl } from '../../lib/api'
import { withSpan } from '../../instrumentation'
import { chatErrorMessage } from '../../utils/chatError'

/** The chat is throttled per signed-in user, or per IP for guests (#1049), so send the sign-in token when there is one. */
function chatHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  try {
    const token = localStorage.getItem('auth_token')
    if (token) headers.Authorization = `Bearer ${token}`
  } catch {
    // Storage blocked: chat as a guest.
  }
  return headers
}

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

export type MeetingChatThreadMeta = {
  id: string
  title: string
  updatedAt: number
}

type StoredThread = MeetingChatThreadMeta & { messages: ChatMessage[] }

const STORAGE_KEY = 'on_meeting_chat_threads_v1'

function welcomeMessage(): ChatMessage {
  return {
    id: 'welcome',
    role: 'assistant',
    content:
      'Ask about local meetings in this scope. I answer from meeting summaries and cite the meetings I used. Ask for a quote when you need transcript detail.',
    citations: [],
    found: true,
  }
}

function convertMessage(message: ChatMessage): ThreadMessageLike {
  return {
    id: message.id,
    role: message.role,
    content: [{ type: 'text', text: message.content }],
  }
}

function titleFromMessages(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === 'user')
  if (!firstUser) return 'New chat'
  const t = firstUser.content.trim().replace(/\s+/g, ' ')
  return t.length > 48 ? `${t.slice(0, 48)}…` : t
}

function loadStore(): { threads: StoredThread[]; activeId: string } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) throw new Error('empty')
    const parsed = JSON.parse(raw) as { threads?: StoredThread[]; activeId?: string }
    const threads = Array.isArray(parsed.threads) ? parsed.threads : []
    if (!threads.length) throw new Error('none')
    const activeId =
      threads.some((t) => t.id === parsed.activeId) && parsed.activeId
        ? parsed.activeId
        : threads[0].id
    return { threads, activeId }
  } catch {
    const id = crypto.randomUUID()
    return {
      threads: [
        {
          id,
          title: 'New chat',
          updatedAt: Date.now(),
          messages: [welcomeMessage()],
        },
      ],
      activeId: id,
    }
  }
}

type ChatControls = {
  threads: MeetingChatThreadMeta[]
  activeId: string
  isRunning: boolean
  newChat: () => void
  selectThread: (id: string) => void
  deleteThread: (id: string) => void
}

const MeetingChatControlsContext = createContext<ChatControls | null>(null)

export function useMeetingChatControls(): ChatControls {
  const ctx = useContext(MeetingChatControlsContext)
  if (!ctx) {
    throw new Error('useMeetingChatControls must be used inside MeetingChatRuntimeProvider')
  }
  return ctx
}

export function MeetingChatRuntimeProvider({
  scope,
  children,
}: {
  scope: MeetingChatScope
  children: ReactNode
}) {
  const initial = useMemo(() => loadStore(), [])
  const [threads, setThreads] = useState<StoredThread[]>(initial.threads)
  const [activeId, setActiveId] = useState(initial.activeId)
  const [isRunning, setIsRunning] = useState(false)

  const active = threads.find((t) => t.id === activeId) ?? threads[0]
  const messages = active?.messages ?? [welcomeMessage()]

  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          threads: threads.map((t) => ({
            ...t,
            // Cap stored history so localStorage stays small
            messages: t.messages.slice(-40),
          })),
          activeId,
        }),
      )
    } catch {
      // private mode / quota — ignore
    }
  }, [threads, activeId])

  const setActiveMessages = useCallback(
    (updater: (prev: ChatMessage[]) => ChatMessage[]) => {
      setThreads((prev) =>
        prev.map((t) => {
          if (t.id !== activeId) return t
          const nextMsgs = updater(t.messages)
          return {
            ...t,
            messages: nextMsgs,
            title: titleFromMessages(nextMsgs),
            updatedAt: Date.now(),
          }
        }),
      )
    },
    [activeId],
  )

  const newChat = useCallback(() => {
    const id = crypto.randomUUID()
    setThreads((prev) => [
      {
        id,
        title: 'New chat',
        updatedAt: Date.now(),
        messages: [welcomeMessage()],
      },
      ...prev,
    ])
    setActiveId(id)
  }, [])

  const selectThread = useCallback((id: string) => {
    setActiveId(id)
  }, [])

  const deleteThread = useCallback(
    (id: string) => {
      setThreads((prev) => {
        const next = prev.filter((t) => t.id !== id)
        if (!next.length) {
          const nid = crypto.randomUUID()
          setActiveId(nid)
          return [
            {
              id: nid,
              title: 'New chat',
              updatedAt: Date.now(),
              messages: [welcomeMessage()],
            },
          ]
        }
        if (id === activeId) setActiveId(next[0].id)
        return next
      })
    },
    [activeId],
  )

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const part = message.content[0]
      if (!part || part.type !== 'text') {
        throw new Error('Only text messages are supported')
      }
      const input = part.text.trim()
      if (!input) return

      setActiveMessages((prev) => [
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
              headers: chatHeaders(),
              signal: controller.signal,
              body: JSON.stringify({
                question: input,
                state: scope.state || undefined,
                city: scope.city || undefined,
                county_fips: scope.county_fips || undefined,
              }),
            })
            const body = (await res.json().catch(() => null)) as (ChatApiResponse & { detail?: string }) | null
            if (!res.ok || !body) {
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
        setActiveMessages((prev) => [
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
        // Say what actually happened: the server's reason, a timeout, or no connection (#916).
        const detail = chatErrorMessage(err).text
        setActiveMessages((prev) => [
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
    [scope.state, scope.city, scope.county_fips, setActiveMessages],
  )

  const runtime = useExternalStoreRuntime({
    isRunning,
    messages,
    convertMessage,
    onNew,
  })

  const controls = useMemo<ChatControls>(
    () => ({
      threads: threads
        .map(({ id, title, updatedAt }) => ({ id, title, updatedAt }))
        .sort((a, b) => b.updatedAt - a.updatedAt),
      activeId,
      isRunning,
      newChat,
      selectThread,
      deleteThread,
    }),
    [threads, activeId, isRunning, newChat, selectThread, deleteThread],
  )

  return (
    <MeetingChatControlsContext.Provider value={controls}>
      <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>
    </MeetingChatControlsContext.Provider>
  )
}
