/**
 * Source data for the video.
 *
 * Phoenix City Council Formal Meeting — April 8, 2026 (event_id 1871047097,
 * video CGDA6fZy7Ok). Of the five decisions surfaced by Open Navigator's policy
 * frame-analysis, decision D004 is the most controversial: it is the only one
 * pairing a SPLIT VOTE (8-1) with charged civil-liberties subject matter
 * (ICE collaboration, hate-group monitoring, the definition of "terrorism").
 *
 * Everything below is lifted verbatim from the analysis record so the script is
 * grounded in the real frame analysis, not invented.
 */

export const MEETING = {
  body: 'Phoenix City Council',
  dateLabel: 'April 8, 2026',
  jurisdiction: 'Phoenix, AZ',
  agendaItem: 'Item 43',
  videoId: 'CGDA6fZy7Ok',
};

export const DECISION = {
  id: 'D004',
  headline:
    'Council Accepts Homeland Security Grant Funds Amidst Concerns Over Hate Group Monitoring and ICE Collaboration',
  oneBigThing:
    "The City Council accepted federal Homeland Security grant funds despite concerns about how 'terrorism' is defined and the monitoring of hate groups.",
  whyItMatters:
    'Provides critical funding for emergency preparedness — but raises questions about civil liberties and not targeting marginalized communities.',
  outcome: 'Approved',
  vote: {yes: 8, no: 1},
  dissenter: 'Councilwoman Hernandez',
  fiscalYear: '2022', // bare calendar year on the wire = string
};

/** The two competing FRAMES — the heart of the "frame analysis". */
export const FRAME_FOR = {
  team: 'TEAM PUBLIC SAFETY',
  who: 'City Staff · Asst. Chief Lee',
  label: 'Accept Grant Funds for Public Safety',
  problem: 'The city needs federal funds to prevent and respond to terrorism and disasters.',
  story: "Grants are defined by federal DHS/FEMA rules — focus is on criminality, not groups.",
  remedy: 'Take the money. (No ICE tie-in for Phoenix’s grants.)',
};

export const FRAME_AGAINST = {
  team: 'TEAM PROTECT COMMUNITIES',
  who: 'Councilwoman Hernandez',
  label: 'Ensure Accountability and Protect Communities',
  problem: "The definition of 'terrorism-related risk' is far too broad.",
  story: 'History shows Black & Brown groups get labeled threats and profiled.',
  remedy: 'Add guardrails. Aim at hate groups, not communities. No ICE — ever.',
};

/** Lightning-round stats pulled from evidence_metrics + smart_brevity. */
export const STATS = [
  {big: 'FY 2022', small: 'reallocated federal Homeland Security funds'},
  {big: '38', small: 'active AZ hate groups — SPLC, 2023 report'},
  {big: '8 – 1', small: 'the final vote · one lone dissenter'},
];
