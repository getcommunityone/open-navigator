/**
 * Which pipeline stage a live Run-all / Run-each log is currently in.
 * Used so expanding Videos does not dump Discover output (#753 + #755).
 */
export type FullRunPhase =
  | 'discover'
  | 'videos'
  | 'transcripts'
  | 'analyses'
  | 'reports'

const STAGE_FOR_PHASE: Record<FullRunPhase, string[]> = {
  discover: ['discover'],
  videos: ['videos'],
  transcripts: ['transcripts'],
  analyses: ['analyses', 'analyses_light'],
  reports: ['reports', 'reports_light'],
}

/**
 * Infer the active full-run phase from log tail lines / current banner.
 * Last matching stage banner wins. Defaults to Discover for Run all (#755)
 * when the log has not reached Catalog yet.
 */
export function fullRunPhaseFromLog(
  lines: string[],
  current: string = '',
  opts: { step?: 'all' | 'each' | null } = {},
): FullRunPhase | null {
  const step = opts.step === undefined ? 'all' : opts.step
  if (!step) return null
  let phase: FullRunPhase | null = step === 'all' ? 'discover' : 'videos'
  for (const raw of [...lines, current]) {
    const s = (raw || '').toLowerCase()
    if (!s.trim()) continue
    if (
      s.includes('=== discover') ||
      s.includes('discover (channel') ||
      s.includes('--- discover')
    ) {
      phase = 'discover'
      continue
    }
    if (
      s.includes('=== catalog') ||
      s.includes('catalog →') ||
      s.includes('--- catalog:')
    ) {
      phase = 'videos'
      continue
    }
    if (
      (s.includes('=== caption') ||
        s.includes('--- caption') ||
        s.includes('=== transcript') ||
        s.includes('backfill')) &&
      !s.includes('catalog')
    ) {
      phase = 'transcripts'
      continue
    }
    if (s.includes('=== analyz') || s.includes('--- analyz') || s.includes('analyze-light')) {
      phase = 'analyses'
      continue
    }
    if (s.includes('=== report') || s.includes('--- report') || s.includes('reports-light')) {
      phase = 'reports'
    }
  }
  return phase
}

/** True when the expanded dashboard stage should tail the shared all/each log. */
export function stageOwnsFullRunLog(
  expandedStage: string | null,
  phase: FullRunPhase | null,
): boolean {
  if (!expandedStage || !phase) return false
  return (STAGE_FOR_PHASE[phase] ?? []).includes(expandedStage)
}

/** Human label for the waiting banner. */
export function fullRunPhaseLabel(phase: FullRunPhase | null): string {
  switch (phase) {
    case 'discover':
      return 'Discover'
    case 'videos':
      return 'Videos (catalog)'
    case 'transcripts':
      return 'Transcripts'
    case 'analyses':
      return 'Analyses'
    case 'reports':
      return 'Reports'
    default:
      return 'another stage'
  }
}
