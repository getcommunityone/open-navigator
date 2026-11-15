import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  adminCheckApplicationLink,
  adminCreateApplicationLink,
  adminDeleteApplicationLink,
  adminListApplicationLinks,
  adminUpdateApplicationLink,
  adminVerifyApplicationLink,
  type AdminApplicationLink,
} from '../api/applicationLinks'
import { formatIsoDate, verifiedLabel } from '../lib/dataCenterJobs'

/**
 * /admin/application-links — admins keep the job-application links for data
 * center projects (issue #248, DC-1.3).
 *
 * Every link records when it was last verified: by "Check now" (the server
 * requests the page; a live answer counts) or by "Mark verified" (an admin opened
 * it and the posting is open). Links not verified in 30 days are flagged Stale.
 * The routes behind this page require an admin (`require_admin`).
 */

interface FormState {
  project_name: string
  employer: string
  state_code: string
  city: string
  url: string
  source_note: string
}

const EMPTY: FormState = { project_name: '', employer: '', state_code: '', city: '', url: '', source_note: '' }

const QUERY_KEY = ['admin', 'application-links'] as const

/** The API's own reason when it gave one ("That URL is already in the list"), else the HTTP status. */
function errorText(err: unknown): string {
  const e = err as { message?: string; response?: { data?: { detail?: unknown } } } | undefined
  const detail = e?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => (d as { msg?: string })?.msg).filter(Boolean)
    if (msgs.length) return msgs.join('; ')
  }
  return e?.message ?? 'Something went wrong.'
}

function checkLabel(link: AdminApplicationLink): string {
  if (!link.last_check_status) return 'Not checked yet'
  const when = formatIsoDate(link.last_checked_at)
  const code = link.last_http_status != null ? ` (HTTP ${link.last_http_status})` : ''
  const word = { live: 'Page answered', dead: 'Page gone', error: 'Check failed' }[link.last_check_status]
  return `${word}${code}${when ? ` · ${when}` : ''}`
}

export default function ApplicationLinksAdminPage() {
  const qc = useQueryClient()
  const [staleOnly, setStaleOnly] = useState(false)
  const [form, setForm] = useState<FormState>(EMPTY)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: [...QUERY_KEY, staleOnly],
    queryFn: () => adminListApplicationLinks(staleOnly),
  })

  const refresh = () => qc.invalidateQueries({ queryKey: QUERY_KEY })
  const onError = (err: unknown) => setMessage(errorText(err))

  const save = useMutation({
    mutationFn: async (f: FormState) => {
      const body = {
        project_name: f.project_name,
        employer: f.employer || null,
        state_code: f.state_code,
        city: f.city || null,
        url: f.url,
        source_note: f.source_note || null,
      }
      return editingId == null ? adminCreateApplicationLink(body) : adminUpdateApplicationLink(editingId, body)
    },
    onSuccess: () => {
      setMessage(editingId == null ? 'Link added. Check it or mark it verified.' : 'Link updated.')
      setForm(EMPTY)
      setEditingId(null)
      refresh()
    },
    onError,
  })
  const check = useMutation({ mutationFn: adminCheckApplicationLink, onSuccess: refresh, onError })
  const verify = useMutation({ mutationFn: adminVerifyApplicationLink, onSuccess: refresh, onError })
  const remove = useMutation({ mutationFn: adminDeleteApplicationLink, onSuccess: refresh, onError })

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setMessage(null)
    save.mutate(form)
  }

  const startEdit = (link: AdminApplicationLink) => {
    setEditingId(link.job_application_link_id)
    setForm({
      project_name: link.project_name,
      employer: link.employer ?? '',
      state_code: link.state_code,
      city: link.city ?? '',
      url: link.url,
      source_note: link.source_note ?? '',
    })
    setMessage(null)
  }

  const field = (key: keyof FormState, label: string, opts: { required?: boolean; type?: string; placeholder?: string } = {}) => (
    <label className="flex flex-col gap-1 text-xs font-medium text-slate-700">
      {label}
      <input
        type={opts.type ?? 'text'}
        required={opts.required}
        placeholder={opts.placeholder}
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        className="rounded border border-slate-300 px-2 py-1.5 text-sm font-normal text-slate-900"
      />
    </label>
  )

  const items = data?.items ?? []
  const busy = check.isPending || verify.isPending || remove.isPending

  return (
    <div className="space-y-3">
      <form onSubmit={submit} className="rounded-lg border border-slate-300 bg-white p-3 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900">
          {editingId == null ? 'Add an application link' : 'Edit application link'}
        </h2>
        <p className="mb-2 text-xs text-slate-600">
          A link for applying to jobs at a data center project. Changing the URL clears its verification.
        </p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {field('project_name', 'Project', { required: true, placeholder: 'As named in meetings' })}
          {field('employer', 'Employer')}
          {field('url', 'Application URL', { required: true, type: 'url', placeholder: 'https://' })}
          {field('state_code', 'State', { required: true, placeholder: 'AL' })}
          {field('city', 'City')}
          {field('source_note', 'Where you found it')}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button
            type="submit"
            disabled={save.isPending}
            className="rounded bg-teal-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-50"
          >
            {editingId == null ? 'Add link' : 'Save changes'}
          </button>
          {editingId != null && (
            <button
              type="button"
              onClick={() => {
                setEditingId(null)
                setForm(EMPTY)
              }}
              className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700"
            >
              Cancel
            </button>
          )}
          {message && (
            <span role="status" className="text-xs text-slate-700">
              {message}
            </span>
          )}
        </div>
      </form>

      <section className="rounded-lg border border-slate-300 bg-white p-3 shadow-sm">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold text-slate-900">
            Application links
            {data && (
              <span className="ml-2 text-sm font-normal text-slate-600">
                {data.total} {staleOnly ? 'stale' : 'total'}
                {!staleOnly && ` · ${data.stale} stale`}
              </span>
            )}
          </h2>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={staleOnly} onChange={(e) => setStaleOnly(e.target.checked)} />
            Only stale (not verified in 30 days)
          </label>
        </div>

        {isLoading ? (
          <p role="status" className="text-sm text-slate-500">Loading…</p>
        ) : isError ? (
          <p role="alert" className="text-sm text-red-700">Couldn&apos;t load links: {errorText(error)}</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-slate-600">{staleOnly ? 'No stale links.' : 'No application links yet.'}</p>
        ) : (
          <ul className="divide-y divide-slate-200">
            {items.map((link) => (
              <li key={link.job_application_link_id} className="py-2">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-medium text-slate-900">
                    {link.project_name}
                    {link.employer && <span className="font-normal text-slate-600"> · {link.employer}</span>}
                    <span className="font-normal text-slate-500">
                      {' '}
                      · {[link.city, link.state_code].filter(Boolean).join(', ')}
                    </span>
                  </p>
                  {link.is_stale && (
                    <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800">Stale</span>
                  )}
                </div>
                <a
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="break-all text-sm text-teal-800 underline"
                >
                  {link.url}
                </a>
                <p className="text-xs text-slate-600">
                  {verifiedLabel(link.last_verified_at, link.is_stale)} · {checkLabel(link)}
                  {link.source_note && ` · Source: ${link.source_note}`}
                </p>
                <div className="mt-1 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => check.mutate(link.job_application_link_id)}
                    className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                  >
                    Check now
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => verify.mutate(link.job_application_link_id)}
                    className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                    title="You opened the page and the posting is open"
                  >
                    Mark verified
                  </button>
                  <button
                    type="button"
                    onClick={() => startEdit(link)}
                    className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-800 hover:bg-slate-50"
                  >
                    Edit
                  </button>
                  <DeleteButton disabled={busy} onConfirm={() => remove.mutate(link.job_application_link_id)} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

/** Two-step delete without a browser confirm() dialog. */
function DeleteButton({ disabled, onConfirm }: { disabled: boolean; onConfirm: () => void }) {
  const [armed, setArmed] = useState(false)
  if (!armed) {
    return (
      <button
        type="button"
        disabled={disabled}
        onClick={() => setArmed(true)}
        className="rounded border border-red-200 px-2 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50"
      >
        Delete
      </button>
    )
  }
  return (
    <span className="inline-flex gap-1">
      <button
        type="button"
        onClick={() => {
          setArmed(false)
          onConfirm()
        }}
        className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700"
      >
        Delete for good
      </button>
      <button type="button" onClick={() => setArmed(false)} className="rounded border border-slate-300 px-2 py-1 text-xs">
        Keep
      </button>
    </span>
  )
}
