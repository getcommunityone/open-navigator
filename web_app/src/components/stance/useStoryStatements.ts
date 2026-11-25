import { useCallback, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  errorStatus,
  fetchStanceResults,
  postStanceResponse,
  type PackResults,
  type StanceAnswer,
  type StancePack,
  type StanceStatement,
  type StatementResults,
} from '../../api/stance'

/** One story screen's statement and everything its answer block needs (#981). */
export interface ScreenStatement {
  statement: StanceStatement
  results: StatementResults | undefined
  minSample: number | null
  answer: StanceAnswer | null
  posting: boolean
  error: string | null
  changing: boolean
  onAnswer: (a: StanceAnswer) => void
  onChange: () => void
}

/**
 * The pack's statements by the story screen that asks them, the readers' results for the story's place, and saving an
 * answer. Answers go to the same store as the Challenge used, so an earlier answer shows as the reader's own.
 */
export function useStoryStatements(
  pack: StancePack | undefined,
  playerId: string,
  stateCode: string | undefined,
  city: string | null,
): Map<string, ScreenStatement> {
  const qc = useQueryClient()
  const packId = pack?.pack_id ?? ''
  const key = useMemo(() => ['stance', 'results', packId, stateCode ?? '', (stateCode && city) || '', playerId], [packId, stateCode, city, playerId])
  const resultsQ = useQuery({
    queryKey: key,
    queryFn: () => fetchStanceResults(packId, { stateCode, placeName: (stateCode && city) || undefined, playerId }),
    enabled: Boolean(packId),
    staleTime: 60_000,
    retry: 1,
  })
  const [posting, setPosting] = useState<string | null>(null)
  const [errors, setErrors] = useState<Record<string, string | null>>({})
  const [changing, setChanging] = useState<Record<string, boolean>>({})

  const answer = useCallback(
    async (statementId: string, a: StanceAnswer) => {
      if (!packId || posting) return
      setPosting(statementId)
      setErrors((e) => ({ ...e, [statementId]: null }))
      try {
        const out = await postStanceResponse({
          player_id: playerId,
          pack_id: packId,
          statement_id: statementId,
          answer: a,
          state_code: stateCode,
          place_name: (stateCode && city) || undefined,
        })
        qc.setQueryData<PackResults>(key, (old) =>
          old
            ? {
                ...old,
                statements: old.statements.some((s) => s.statement_id === statementId)
                  ? old.statements.map((s) => (s.statement_id === statementId ? { ...out.results, your_answer: out.stance_response.answer } : s))
                  : [...old.statements, { ...out.results, your_answer: out.stance_response.answer }],
              }
            : old,
        )
        setChanging((c) => ({ ...c, [statementId]: false }))
      } catch (e) {
        const msg =
          errorStatus(e) === 429
            ? 'Too many answers just now. Wait a little, then try again. Your answer was not saved.'
            : 'Your answer could not be saved. Check your connection, then try again.'
        setErrors((er) => ({ ...er, [statementId]: msg }))
      } finally {
        setPosting(null)
      }
    },
    [packId, posting, playerId, stateCode, city, qc, key],
  )

  return useMemo(() => {
    const out = new Map<string, ScreenStatement>()
    const byId = new Map((resultsQ.data?.statements ?? []).map((s) => [s.statement_id, s]))
    for (const st of pack?.statements ?? []) {
      if (!st.story_screen) continue
      const results = byId.get(st.statement_id)
      out.set(st.story_screen, {
        statement: st,
        results,
        minSample: resultsQ.data?.min_sample ?? null,
        answer: (results?.your_answer as StanceAnswer | null | undefined) ?? null,
        posting: posting === st.statement_id,
        error: errors[st.statement_id] ?? null,
        changing: Boolean(changing[st.statement_id]),
        onAnswer: (a) => void answer(st.statement_id, a),
        onChange: () => setChanging((c) => ({ ...c, [st.statement_id]: true })),
      })
    }
    return out
  }, [pack, resultsQ.data, posting, errors, changing, answer])
}
