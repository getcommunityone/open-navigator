/**
 * The search term behind a company's meeting count (#1043): the name actually said in its newest quote (the text the
 * server marked with <mark>), so "5 meetings" for Expedia Group searches "VRBO" rather than its first alias "HomeAway",
 * which no meeting says. Without a quote, the company's own name.
 */
export function companySearchTerm(companyName: string, evidence?: string | null): string {
  const m = /<mark>([^<]+)<\/mark>/i.exec(evidence ?? '')
  const said = m?.[1]?.trim()
  return said || companyName
}
