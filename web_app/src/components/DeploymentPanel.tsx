import { useQuery } from '@tanstack/react-query'
import { useCallback, useMemo, useState } from 'react'
import {
  fetchDeployments,
  fetchDeploymentLog,
  launchDeployment,
  stopDeployment,
  type DeploymentJob,
  type DeploymentStep,
} from '../api/deployments'
import { formatAgoCompact, formatDateTimeAbsolute } from '../utils/dateTime'

const STATUS_STYLE: Record<string, string> = {
  completed: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  running: 'bg-sky-100 text-sky-800 border-sky-200',
  failed: 'bg-red-100 text-red-800 border-red-200',
  cancelled: 'bg-amber-100 text-amber-800 border-amber-200',
  skipped: 'bg-slate-100 text-slate-500 border-slate-200',
  pending: 'bg-slate-100 text-slate-500 border-slate-200',
}

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_STYLE[status] ?? STATUS_STYLE.pending
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${cls}`}
    >
      {status === 'running' && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-500" />
      )}
      {status}
    </span>
  )
}

function StepRow({ job, step }: { job: DeploymentJob; step: DeploymentStep }) {
  const [open, setOpen] = useState(false)
  const { data: log, isFetching } = useQuery({
    queryKey: ['deployment-log', job.job_id, step.key],
    queryFn: () => fetchDeploymentLog(job.job_id, step.key),
    enabled: open,
    // Keep the log fresh while the step is actively running.
    refetchInterval: open && step.status === 'running' ? 3_000 : false,
  })

  return (
    <div className="rounded-md border border-slate-200">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-slate-50"
      >
        <span className="flex items-center gap-2">
          <span className="text-slate-400">{open ? '▾' : '▸'}</span>
          <span className="text-sm font-medium text-slate-800">{step.label}</span>
          <span className="text-xs text-slate-500">{step.description}</span>
        </span>
        <span className="flex items-center gap-3">
          {step.exit_code != null && step.status !== 'completed' && (
            <span className="text-xs text-slate-500">exit {step.exit_code}</span>
          )}
          <StatusBadge status={step.status} />
        </span>
      </button>
      {open && (
        <div className="border-t border-slate-100 bg-slate-50 px-3 py-2">
          {step.cmd && (
            <p className="mb-1 font-mono text-[11px] text-slate-500">$ {step.cmd}</p>
          )}
          {isFetching && !log && (
            <p className="text-xs text-slate-400">Loading log…</p>
          )}
          {log && log.lines.length > 0 ? (
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded bg-slate-900 p-2 font-mono text-[11px] leading-relaxed text-slate-100">
              {log.lines.join('\n')}
            </pre>
          ) : (
            !isFetching && <p className="text-xs text-slate-400">No log output yet.</p>
          )}
        </div>
      )}
    </div>
  )
}

function stepSummary(job: DeploymentJob): string {
  const total = job.steps.length
  const done = job.steps.filter((s) => s.status === 'completed').length
  const failed = job.steps.filter((s) => s.status === 'failed').length
  const parts = [`${total} step${total === 1 ? '' : 's'}`]
  if (done) parts.push(`${done} done`)
  if (failed) parts.push(`${failed} failed`)
  return parts.join(' · ')
}

function JobCard({
  job,
  onStop,
  clockMs,
  defaultOpen = false,
}: {
  job: DeploymentJob
  onStop: (jobId: string) => void
  clockMs: number
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  const when = job.started_at ? formatDateTimeAbsolute(job.started_at) : '—'
  const ago = job.started_at ? formatAgoCompact(job.started_at, clockMs) : null
  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 p-4">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex flex-1 items-start gap-2 text-left"
        >
          <span className="mt-0.5 text-slate-400">{open ? '▾' : '▸'}</span>
          <span>
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-slate-900">{job.label}</span>
              {job.dry_run && (
                <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700">
                  DRY RUN
                </span>
              )}
              <StatusBadge status={job.status} />
              {!open && (
                <span className="text-[11px] text-slate-500">{stepSummary(job)}</span>
              )}
            </span>
            <span className="mt-0.5 block font-mono text-[11px] text-slate-400">
              {job.job_id} · started {when}
              {ago ? ` (${ago})` : ''}
            </span>
          </span>
        </button>
        {job.live && job.status === 'running' && (
          <button
            type="button"
            onClick={() => onStop(job.job_id)}
            className="rounded-md border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100"
          >
            Stop
          </button>
        )}
      </div>
      {open && (
        <div className="space-y-2 border-t border-slate-100 p-4">
          {job.steps.map((s) => (
            <StepRow key={s.key} job={job} step={s} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function DeploymentPanel() {
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['deployments'],
    queryFn: fetchDeployments,
    refetchInterval: (q) => {
      const live = q.state.data?.jobs?.some((j) => j.live && j.status === 'running')
      return live ? 3_000 : 15_000
    },
    retry: 1,
  })

  const availableSteps = data?.available_steps ?? []
  const enabled = data?.enabled ?? false

  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [dryRun, setDryRun] = useState(true)
  const [launching, setLaunching] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  // Default selection = every available step, once they load.
  const effectiveSelected = useMemo(() => {
    if (selected.size > 0) return selected
    return new Set(availableSteps.map((s) => s.key))
  }, [selected, availableSteps])

  const toggleStep = useCallback(
    (key: string) => {
      setSelected((prev) => {
        const base = prev.size > 0 ? new Set(prev) : new Set(availableSteps.map((s) => s.key))
        if (base.has(key)) base.delete(key)
        else base.add(key)
        return base
      })
    },
    [availableSteps],
  )

  const anyLive = data?.jobs?.some((j) => j.live && j.status === 'running') ?? false

  const onLaunch = useCallback(async () => {
    const steps = availableSteps.map((s) => s.key).filter((k) => effectiveSelected.has(k))
    if (steps.length === 0) {
      setMsg('Select at least one step.')
      return
    }
    if (!dryRun) {
      const ok = window.confirm(
        `Run a REAL production deployment (${steps.join(', ')})?\n\n` +
          'This pushes to the Neon prod database and/or HuggingFace. This cannot be undone.',
      )
      if (!ok) return
    }
    setLaunching(true)
    setMsg(null)
    try {
      const res = await launchDeployment({ steps, dry_run: dryRun })
      setMsg(res.detail || 'Launched.')
      window.setTimeout(() => void refetch(), 1_000)
    } catch (e) {
      setMsg((e as Error).message || 'Launch failed')
    } finally {
      setLaunching(false)
    }
  }, [availableSteps, effectiveSelected, dryRun, refetch])

  const onStop = useCallback(
    async (jobId: string) => {
      if (!window.confirm(`Stop deployment ${jobId}? The running step is terminated.`)) return
      try {
        const res = await stopDeployment(jobId)
        setMsg(res.detail)
        void refetch()
      } catch (e) {
        setMsg((e as Error).message || 'Stop failed')
      }
    },
    [refetch],
  )

  const clockMs = Date.now()

  return (
    <div className="space-y-4">
      {/* Launch control */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Launch a prod deployment</h2>
        <p className="mt-0.5 text-xs text-slate-500">
          Runs the selected steps in order. A failing step stops the run.
        </p>

        <div className="mt-3 flex flex-wrap gap-2">
          {availableSteps.map((s) => {
            const on = effectiveSelected.has(s.key)
            return (
              <button
                key={s.key}
                type="button"
                onClick={() => toggleStep(s.key)}
                title={s.description}
                className={`rounded-md border px-3 py-1.5 text-xs font-medium ${
                  on
                    ? 'border-sky-300 bg-sky-50 text-sky-800'
                    : 'border-slate-200 bg-white text-slate-500'
                }`}
              >
                <span className="mr-1">{on ? '✓' : '○'}</span>
                {s.label}
              </button>
            )
          })}
          {availableSteps.length === 0 && (
            <span className="text-xs text-slate-400">No deployment steps available.</span>
          )}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-xs text-slate-700">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="h-3.5 w-3.5"
            />
            Dry run (log commands, don&apos;t execute)
          </label>
          <button
            type="button"
            onClick={onLaunch}
            disabled={launching || (!dryRun && !enabled) || anyLive}
            className={`rounded-md px-4 py-1.5 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50 ${
              dryRun ? 'bg-indigo-600 hover:bg-indigo-700' : 'bg-red-600 hover:bg-red-700'
            }`}
          >
            {launching
              ? 'Launching…'
              : dryRun
                ? '▶ Launch dry run'
                : '▶ Deploy to PRODUCTION'}
          </button>
          {anyLive && (
            <span className="text-xs text-amber-600">
              A deployment is already running — stop it before launching another.
            </span>
          )}
        </div>

        {!dryRun && !enabled && (
          <p className="mt-2 text-xs text-amber-700">
            Real deploys are disabled. Set <code>DEPLOYMENTS_ALLOW_LAUNCH=1</code> on the API to
            enable, or keep Dry run on.
          </p>
        )}
        {msg && <p className="mt-2 text-xs text-slate-600">{msg}</p>}
      </div>

      {/* Recent jobs */}
      {isPending && !data && (
        <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          Loading deployments…
        </div>
      )}
      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          Could not load deployments: {(error as Error)?.message ?? 'error'}{' '}
          <button type="button" className="underline" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}
      {data && data.jobs.length === 0 && (
        <div className="rounded-lg border border-dashed border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No deployments yet. Launch one above.
        </div>
      )}
      {data?.jobs.map((job) => (
        <JobCard key={job.job_id} job={job} onStop={onStop} clockMs={clockMs} />
      ))}
    </div>
  )
}
