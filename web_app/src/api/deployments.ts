// Client for the prod-deployment batch-job kind (database → Neon prod,
// web → HuggingFace). These endpoints aren't in the generated OpenAPI types, so
// we use plain fetch (matching the launch helpers in ./batchJobs.ts).
//
// Every endpoint here is admin-gated on the backend (require_admin), so all
// requests carry the bearer token via authHeaders().
import { authHeaders } from '../lib/authHeader'
import { tracedFetch } from '../lib/api'

export type DeploymentStep = {
  key: string
  label: string
  description: string
  target: string
  status: string
  started_at?: string | null
  finished_at?: string | null
  exit_code?: number | null
  note?: string | null
  log: string
  cmd: string
  /** Counts recorded by the step (#823); null when it left no result file. */
  counts?: Record<string, number> | null
  result?: string | null
}

export type StepResultReason = {
  reason: string
  outcome: string
  label: string
  advice: string
  count: number
}

export type StepResultItem = {
  file: string
  video_id?: string | null
  tier?: string | null
  outcome: string
  reason: string
  detail?: string | null
}

export type StepResult = {
  job_id: string
  step: string
  /** False when the step left no result file (older runs, dry runs). */
  available: boolean
  kind: string
  dry_run: boolean
  counts: Record<string, number>
  reasons: StepResultReason[]
  total: number
  rows: StepResultItem[]
}

export type DeploymentJob = {
  job_id: string
  job_type: string
  /** 'load' or 'deploy'. */
  group?: string
  label: string
  dry_run: boolean
  pid?: number | null
  status: string
  started_at?: string | null
  updated_at?: string | null
  finished_at?: string | null
  steps: DeploymentStep[]
  /** True while the orchestrator process is still alive. */
  live: boolean
}

/** ``load`` = tab "2 Load" (analysis files → bronze → dbt gold); ``deploy`` = tab "3 Deploy". */
export type DeploymentGroup = 'load' | 'deploy'

export type DeploymentStepDef = {
  key: string
  label: string
  description: string
  target: string
  group?: DeploymentGroup
}

export type DeploymentsListPayload = {
  jobs: DeploymentJob[]
  available_steps: DeploymentStepDef[]
  /** Whether real (non-dry-run) deploys are enabled (DEPLOYMENTS_ALLOW_LAUNCH). */
  enabled: boolean
}

export type LaunchDeploymentResult = {
  launched: boolean
  job_id: string
  pid?: number | null
  dry_run: boolean
  steps: string[]
  detail: string
}

export type DeploymentLog = {
  job_id: string
  step: string
  path: string
  lines: string[]
}

async function readError(r: Response): Promise<string> {
  let detail = `HTTP ${r.status}`
  try {
    const j = (await r.json()) as { error?: string; detail?: string }
    if (j?.error || j?.detail) detail = (j.error || j.detail) as string
  } catch {
    /* ignore */
  }
  return detail
}

export async function fetchDeployments(
  group?: DeploymentGroup,
): Promise<DeploymentsListPayload> {
  const r = await tracedFetch(`/api/deployments/${group ? `?group=${group}` : ''}`, {
    headers: authHeaders(),
    signal: AbortSignal.timeout(15_000),
  })
  if (!r.ok) throw new Error(await readError(r))
  return (await r.json()) as DeploymentsListPayload
}

export async function launchDeployment(body: {
  steps?: string[]
  dry_run: boolean
  group?: DeploymentGroup
}): Promise<LaunchDeploymentResult> {
  const r = await tracedFetch('/api/deployments/launch', {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15_000),
  })
  if (!r.ok) throw new Error(await readError(r))
  return (await r.json()) as LaunchDeploymentResult
}

export async function stopDeployment(
  jobId: string,
  force = false,
): Promise<{ stopped: boolean; detail: string }> {
  const r = await tracedFetch(
    `/api/deployments/${encodeURIComponent(jobId)}/stop?force=${force ? 'true' : 'false'}`,
    { method: 'POST', headers: authHeaders(), signal: AbortSignal.timeout(15_000) },
  )
  if (!r.ok) throw new Error(await readError(r))
  return (await r.json()) as { stopped: boolean; detail: string }
}

export async function fetchDeploymentLog(
  jobId: string,
  step: string,
): Promise<DeploymentLog> {
  const r = await tracedFetch(
    `/api/deployments/${encodeURIComponent(jobId)}/log?step=${encodeURIComponent(step)}&lines=300`,
    { headers: authHeaders(), signal: AbortSignal.timeout(10_000) },
  )
  if (!r.ok) throw new Error(await readError(r))
  return (await r.json()) as DeploymentLog
}

export async function fetchStepResult(
  jobId: string,
  step: string,
  opts: { outcome?: string; reason?: string; q?: string; limit?: number; offset?: number } = {},
): Promise<StepResult> {
  const p = new URLSearchParams({ step })
  if (opts.outcome) p.set('outcome', opts.outcome)
  if (opts.reason) p.set('reason', opts.reason)
  if (opts.q) p.set('q', opts.q)
  p.set('limit', String(opts.limit ?? 50))
  p.set('offset', String(opts.offset ?? 0))
  const r = await tracedFetch(`/api/deployments/${encodeURIComponent(jobId)}/result?${p.toString()}`, {
    headers: authHeaders(),
    signal: AbortSignal.timeout(15_000),
  })
  if (!r.ok) throw new Error(await readError(r))
  return (await r.json()) as StepResult
}
