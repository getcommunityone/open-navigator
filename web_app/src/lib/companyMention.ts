import type { QuestionCompanyMention } from '../api/policyQuestions'

// How a company shown on a decision row is labelled (#525). A company the decision's own
// headline/statement names reads "Company named"; one found in a passage of the
// decision's own meeting, where the speaker says it is the applicant or developer, reads
// "Named in the meeting" and can link to the moment in the recording.
export function companyMentionLabel(m: Pick<QuestionCompanyMention, 'evidence_source'>): string {
  return m.evidence_source === 'meeting_passage' ? 'Named in the meeting' : 'Company named'
}

// The recording link for a meeting-passage mention; null for the decision's own text and
// whenever the API has no link (no fake link, no fake time).
export function companyMentionLink(
  m: Pick<QuestionCompanyMention, 'evidence_source' | 'jump_url'>,
): string | null {
  return m.evidence_source === 'meeting_passage' && m.jump_url ? m.jump_url : null
}
