/**
 * ChatGPT-style thread built on assistant-ui primitives, styled to Open Navigator.
 */
import {
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
} from '@assistant-ui/react'

function AssistantBubble() {
  return (
    <MessagePrimitive.Root className="flex justify-start">
      <div className="max-w-[min(100%,40rem)] whitespace-pre-wrap rounded-2xl rounded-tl-md bg-slate-100 px-4 py-3 text-[15px] leading-relaxed text-slate-800">
        <MessagePrimitive.Content />
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

export function MeetingChatThread({ scopeLabel }: { scopeLabel: string }) {
  return (
    <ThreadPrimitive.Root className="flex h-full min-h-[28rem] flex-col bg-gradient-to-b from-slate-50 to-white">
      <div className="border-b border-slate-200/80 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Ask meetings
        </p>
        <p className="text-sm text-slate-700">
          Scope: <span className="font-medium text-primary-700">{scopeLabel}</span>
        </p>
      </div>

      <ThreadPrimitive.Viewport className="flex flex-1 flex-col gap-4 overflow-y-auto px-4 py-4">
        <ThreadPrimitive.Messages
          components={{
            UserMessage: UserBubble,
            AssistantMessage: AssistantBubble,
          }}
        />
        <ThreadPrimitive.ViewportFooter />
      </ThreadPrimitive.Viewport>

      <ComposerPrimitive.Root className="border-t border-slate-200/80 bg-white p-3">
        <div className="flex items-end gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 focus-within:border-primary-500 focus-within:ring-1 focus-within:ring-primary-500">
          <ComposerPrimitive.Input
            placeholder="Ask about budgets, zoning, fluoride…"
            rows={1}
            className="max-h-32 flex-1 resize-none bg-transparent text-[15px] text-slate-800 outline-none placeholder:text-slate-400"
          />
          <ComposerPrimitive.Send className="rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-40">
            Send
          </ComposerPrimitive.Send>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Answers use meeting summaries only unless you ask for a quote. Never invents figures.
        </p>
      </ComposerPrimitive.Root>
    </ThreadPrimitive.Root>
  )
}
