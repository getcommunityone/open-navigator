// Client for the prod-deployment batch-job kind (database → Neon prod,
// web → HuggingFace). These endpoints aren't in the generated OpenAPI types, so
// we use plain fetch (matching the launch helpers in ./batchJobs.ts).

export type DeploymentStep = {
  key: string
  label: string
  description: string
  target: string
  status: string
  started_at?: string | null
  finished_at?: string | null
  exit_code?: number | null
  log: string
  cmd: string
}

export type DeploymentJob = {
  job_id: string
  job_type: string
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

export type DeploymentStepDef = {
  key: string
  label: string
  description: string
  target: string
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

export async function fetchDeployments(): Promise<DeploymentsListPayload> {
  const r = await fetch('/api/deployments/', { signal: AbortSignal.timeout(15_000) })
  if (!r.ok) throw new Error(await readError(r))
  return (await r.json()) as DeploymentsListPayload
}

export async function launchDeployment(body: {
  steps?: string[]
  dry_run: boolean
}): Promise<LaunchDeploymentResult> {
  const r = await fetch('/api/deployments/launch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
  const r = await fetch(
    `/api/deployments/${encodeURIComponent(jobId)}/stop?force=${force ? 'true' : 'false'}`,
    { method: 'POST', signal: AbortSignal.timeout(15_000) },
  )
  if (!r.ok) throw new Error(await readError(r))
  return (await r.json()) as { stopped: boolean; detail: string }
}

export async function fetchDeploymentLog(
  jobId: string,
  step: string,
): Promise<DeploymentLog> {
  const r = await fetch(
    `/api/deployments/${encodeURIComponent(jobId)}/log?step=${encodeURIComponent(step)}&lines=300`,
    { signal: AbortSignal.timeout(10_000) },
  )
  if (!r.ok) throw new Error(await readError(r))
  return (await r.json()) as DeploymentLog
}
