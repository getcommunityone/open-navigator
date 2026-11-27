// One search-category vocabulary for the home search box's "Search in" picker
// and the /search page Filters (#1221). Every entry maps to something
// GET /api/search really returns rows for: `types` is the /search type key and
// `orgType` the ?org_type= organization sub-type (api/routes/search_postgres.py
// ORG_TYPE_PREDICATES). Keep this list honest — add an entry only when the API
// can return it; a type with no rows in scope shows as empty, never invented.

/** Organization sub-types the search API filters on (?org_type=). */
export const ORG_SUBTYPES = [
  { id: 'nonprofit', label: 'Nonprofits' },
  // Private foundations: IRS foundation_code 02/03/04 on the nonprofit record.
  { id: 'foundation', label: 'Foundations' },
  { id: 'church', label: 'Places of worship' },
  { id: 'government', label: 'Government bodies' },
  // org_type business + company (incl. the curated data-center companies).
  { id: 'company', label: 'Companies & businesses' },
  { id: 'healthcare', label: 'Healthcare' },
  { id: 'education', label: 'Schools & education' },
  { id: 'political', label: 'Political groups' },
] as const

export type OrgSubtype = (typeof ORG_SUBTYPES)[number]['id']

export const ORG_SUBTYPE_IDS: readonly string[] = ORG_SUBTYPES.map((s) => s.id)

/** Parse ?org_type= into known sub-types (unknown values dropped, de-duplicated). */
export function parseOrgTypes(raw: string | null | undefined): OrgSubtype[] {
  if (!raw) return []
  const out: OrgSubtype[] = []
  for (const part of raw.split(',')) {
    const v = part.trim().toLowerCase()
    if (ORG_SUBTYPE_IDS.includes(v) && !out.includes(v as OrgSubtype)) out.push(v as OrgSubtype)
  }
  return out
}

/** "Nonprofits", "Nonprofits, Foundations" … for a scope chip; '' when none. */
export function orgTypesLabel(ids: readonly string[]): string {
  return ORG_SUBTYPES.filter((s) => ids.includes(s.id))
    .map((s) => s.label)
    .join(', ')
}

export interface SearchCategory {
  id: string
  label: string
  /** Comma list for ?types= ('' = everything). */
  types: string
  /** ?org_type= sub-type, for the organization sub-type rows. */
  orgType?: OrgSubtype
  /** Rendered indented under its parent (organization sub-types). */
  child?: boolean
}

export const SEARCH_CATEGORIES: SearchCategory[] = [
  { id: 'all', label: 'All', types: '' },
  { id: 'meetings', label: 'Meetings', types: 'meetings' },
  // Meeting transcripts (full-text searched).
  { id: 'transcripts', label: 'Videos', types: 'documents' },
  // Official meeting PDFs (agenda / minutes / attachments), public.event_meeting_document.
  { id: 'meeting_documents', label: 'Meeting Documents', types: 'meeting_documents' },
  { id: 'decisions', label: 'Decisions', types: 'decisions' },
  { id: 'bills', label: 'Bills', types: 'bills' },
  { id: 'topics', label: 'Topics', types: 'topics' },
  { id: 'questions', label: 'Questions', types: 'questions' },
  { id: 'causes', label: 'Causes', types: 'causes' },
  // Government officials (contact_official / person_government).
  { id: 'leaders', label: 'Leaders', types: 'leaders' },
  // Every searchable organization type in the golden org master (mdm_organization).
  { id: 'organizations', label: 'Organizations', types: 'organizations' },
  ...ORG_SUBTYPES.map((s) => ({
    id: `org:${s.id}`,
    label: s.label,
    types: 'organizations',
    orgType: s.id,
    child: true,
  })),
  // Cities, counties, states, school districts … (public.jurisdictions).
  { id: 'jurisdictions', label: 'Places', types: 'jurisdictions' },
  { id: 'grants', label: 'Grants', types: 'grants' },
  { id: 'grant_opportunities', label: 'Grant Opportunities', types: 'grant_opportunities' },
]

/** Every /search type the categories cover (for one counts call). */
export const SEARCH_CATEGORY_TYPES: string[] = Array.from(
  new Set(SEARCH_CATEGORIES.map((c) => c.types).filter(Boolean)),
)

/** The category matching ?types= / ?org_type= (falls back to 'All'). */
export function categoryFromParams(types: string | null, orgType: string | null): SearchCategory {
  const orgTypes = parseOrgTypes(orgType)
  if (types === 'organizations' && orgTypes.length === 1) {
    const hit = SEARCH_CATEGORIES.find((c) => c.orgType === orgTypes[0])
    if (hit) return hit
  }
  return SEARCH_CATEGORIES.find((c) => !c.orgType && c.types === (types ?? '')) ?? SEARCH_CATEGORIES[0]
}

/** Count for a picker row from /search type_totals + org_type_totals; undefined = not counted. */
export function countForCategory(
  c: SearchCategory,
  typeTotals: Record<string, number> | undefined,
  orgTypeTotals: Record<string, number> | undefined,
): number | undefined {
  if (c.id === 'all') return undefined
  if (c.orgType) return orgTypeTotals?.[c.orgType]
  return typeTotals?.[c.types]
}
