/**
 * /admin/operator-actions — open human-required pipeline blockers (#712).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import {
  dismissOperatorAction,
  fetchOperatorActions,
  type OperatorActionItem,
  type OperatorActionTemplate,
} from '../api/batchJobs'

const QUERY_KEY = ['admin', 'operator-actions'] as const

const DOCS_BASE =
  (import.meta.env.VITE_DOCS_URL as string | undefined)?.replace(/\/$/, '') ||
  'http://localhost:3000'

function templateFor(
  templates: OperatorActionTemplate[],
  id: string,
): OperatorActionTemplate | undefined {
  return templates.find((t) => t.id === id)
}

function ActionRow({
  item,
  template,
  onDismiss,
  dismissing,
}: {
  item: OperatorActionItem
  template?: OperatorActionTemplate
  onDismiss: () => void
  dismissing: boolean
}) {
  const [open, setOpen] = useState(true)
  const docsHref = template?.docs_path
    ? `${DOCS_BASE}${template.docs_path}`
    : `${DOCS_BASE}/docs/development/operator-action-templates`

  return (
    <article className="rounded-lg border border-amber-200 bg-amber-50/80 p-3 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-amber-950">{item.title}</h3>
          <p className="mt-0.5 text-xs text-amber-900/80">
            {item.count} occurrence{item.count === 1 ? '' : 's'}
            {item.states?.length ? ` · ${item.states.join(', ')}` : ''}
            {item.detail ? ` — ${item.detail}` : ''}
          </p>
          {item.examples?.length > 0 && (
            <p className="mt-1 font-mono text-[11px] text-slate-700">
              {item.examples.slice(0, 8).join(', ')}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="rounded border border-amber-300 bg-white px-2 py-1 text-xs text-amber-950 hover:bg-amber-100"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? 'Hide steps' : 'Show steps'}
          </button>
          <a
            href={docsHref}
            target="_blank"
            rel="noreferrer"
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-800 hover:bg-slate-50"
          >
            Full playbook
          </a>
          <button
            type="button"
            disabled={dismissing}
            className="rounded border border-slate-400 bg-slate-800 px-2 py-1 text-xs text-white hover:bg-slate-700 disabled:opacity-50"
            onClick={onDismiss}
          >
            Mark resolved
          </button>
        </div>
      </div>
      {open && template && (
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-slate-800">
          {template.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      )}
    </article>
  )
}

export default function OperatorActionsPage() {
  const qc = useQueryClient()
  const [message, setMessage] = useState<string | null>(null)
  const { data, isLoading, isError, error } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: fetchOperatorActions,
    refetchInterval: 15_000,
  })

  const dismiss = useMutation({
    mutationFn: ({ code, fingerprint }: { code: string; fingerprint: string }) =>
      dismissOperatorAction(code, fingerprint),
    onSuccess: (_d, vars) => {
      setMessage(`Resolved ${vars.code}`)
      void qc.invalidateQueries({ queryKey: QUERY_KEY })
    },
    onError: (err) => setMessage((err as Error).message || 'Dismiss failed'),
  })

  const templatesById = useMemo(() => {
    const map = new Map<string, OperatorActionTemplate>()
    for (const t of data?.templates ?? []) map.set(t.id, t)
    return map
  }, [data?.templates])

  return (
    <div className="min-h-0 w-full space-y-4">
      <div>
        <h2 className="text-base font-semibold text-slate-900">Operator actions</h2>
        <p className="mt-0.5 text-xs text-slate-600">
          Human-required pipeline blockers (quota, VPN, API key). Playbooks live in
          docs; this list is the live open set from Discover&apos;s{' '}
          <code>action_required.json</code>.
        </p>
      </div>

      {message && (
        <p className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700">
          {message}
        </p>
      )}

      {isLoading && (
        <p className="text-sm text-slate-500">Loading open actions…</p>
      )}
      {isError && (
        <p className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {(error as Error)?.message || 'Failed to load'}
        </p>
      )}

      {data && (
        <>
          <section className="space-y-2">
            <h3 className="text-sm font-medium text-slate-800">
              Open actions ({data.open.length})
            </h3>
            {data.open.length === 0 ? (
              <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
                No open human actions. A clean Discover write clears blockers
                automatically; Mark resolved hides a stale fingerprint until it
                changes.
              </p>
            ) : (
              data.open.map((item) => (
                <ActionRow
                  key={`${item.code}:${item.fingerprint}`}
                  item={item}
                  template={templateFor(
                    data.templates,
                    item.template_id || item.code,
                  )}
                  dismissing={dismiss.isPending}
                  onDismiss={() =>
                    dismiss.mutate({
                      code: item.code,
                      fingerprint: item.fingerprint,
                    })
                  }
                />
              ))
            )}
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-medium text-slate-800">Templates</h3>
            <ul className="grid gap-2 sm:grid-cols-3">
              {(data.templates ?? []).map((t) => (
                <li
                  key={t.id}
                  className="rounded-lg border border-slate-200 bg-white p-3 text-xs shadow-sm"
                >
                  <p className="font-semibold text-slate-900">{t.title}</p>
                  <p className="mt-0.5 text-slate-600">{t.summary}</p>
                  <a
                    className="mt-2 inline-block text-teal-700 underline"
                    href={`${DOCS_BASE}${t.docs_path}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open playbook
                  </a>
                </li>
              ))}
            </ul>
            {templatesById.size === 0 && (
              <p className="text-xs text-slate-500">No templates returned.</p>
            )}
          </section>

          {data.generated_at && (
            <p className="text-[11px] text-slate-500">
              Source {data.source}
              {data.stamp ? ` · stamp ${data.stamp}` : ''} · generated{' '}
              {data.generated_at}
            </p>
          )}
        </>
      )}
    </div>
  )
}
