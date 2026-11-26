/**
 * Main conversation pane — assistant-ui primitives (#630 / #652).
 */
import {
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  type TextMessagePartComponent,
} from '@assistant-ui/react'
import ChatMarkdown from './ChatMarkdown'

/** Assistant text as formatted markdown: bold, lists and meeting links (#1011). */
const AnswerText: TextMessagePartComponent = ({ text }) => <ChatMarkdown text={text} />

function AssistantBubble() {
  return (
    <MessagePrimitive.Root className="flex justify-start">
      <div className="max-w-[min(100%,40rem)] rounded-2xl rounded-tl-md bg-slate-100 px-4 py-3 text-[15px] leading-relaxed text-slate-800">
        <MessagePrimitive.Content components={{ Text: AnswerText }} />
      </div>
    </MessagePrimitive.Root>
  )
}

function UserBubble() {
  return (
    <MessagePrimitive.Root className="flex justify-end">
      <div className="max-w-[min(100%,40rem)] whitespace-pre-wrap rounded-2xl rounded-tr-md bg-primary-600 px-4 py-3 text-[15px] leading-relaxed text-white">
        <MessagePrimitive.Content />
      </div>
    </MessagePrimitive.Root>
  )
}

export function MeetingChatThread() {
  return (
    <ThreadPrimitive.Root className="flex h-full min-h-0 flex-col bg-gradient-to-b from-slate-50 to-white">
      <ThreadPrimitive.Viewport className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-4 sm:px-6">
        <ThreadPrimitive.Messages
          components={{
            UserMessage: UserBubble,
            AssistantMessage: AssistantBubble,
          }}
        />
        <ThreadPrimitive.ViewportFooter />
      </ThreadPrimitive.Viewport>

      <ComposerPrimitive.Root className="border-t border-slate-200/80 bg-white p-3 sm:px-6">
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 focus-within:border-primary-500 focus-within:ring-1 focus-within:ring-primary-500">
          <ComposerPrimitive.Input
            placeholder="Ask about budgets, zoning, fluoride…"
            rows={1}
            className="max-h-32 min-w-0 flex-1 resize-none bg-transparent text-[15px] text-slate-800 outline-none placeholder:text-slate-400"
          />
          <ComposerPrimitive.Send className="min-h-[44px] shrink-0 rounded-lg bg-primary-600 px-3 py-1.5 sm:min-h-0 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-40">
            Send
          </ComposerPrimitive.Send>
        </div>
        <p className="mx-auto mt-2 max-w-3xl text-xs text-slate-500">
          Never invents figures. Cite only meetings returned for this scope.
        </p>
      </ComposerPrimitive.Root>
    </ThreadPrimitive.Root>
  )
}
