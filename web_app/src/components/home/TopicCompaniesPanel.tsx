import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchTopicCompanies, type TopicCompany } from '../../api/topics'
import { highlightSnippet } from '../../lib/highlight'
import { companySearchTerm } from '../../utils/companySearchTerm'

interface Props {
  /** The curated topic's query id (data-centers, short-term-rentals, license-plate-readers, guns). */
  queryId: string
  /** The topic's name, for the heading. */
  title: string
  stateCode?: string
  city?: string | null
  /** The page's scope label ("National", "Alabama", "Tuscaloosa, Alabama"), shown next to the heading. */
  scopeLabel: string
}

const fmt = (n: number) => n.toLocaleString('en-US')
const fmtDate = (d?: string | null) => {
  if (!d) return null
  const t = new Date(`${d.slice(0, 10)}T12:00:00`)
  return Number.isNaN(t.getTime()) ? null : t.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

/**
 * "Companies named" for the topic chosen in Browse topics (#1052): each company the topic tracks, with the real number of
 * meetings and decisions in scope that name it and its newest mention quoted. Companies never named in scope are listed
 * once, plainly, after the rest; nothing is invented.
 */
export default function TopicCompaniesPanel({ queryId, title, stateCode, city = null, scopeLabel }: Props) {
  const q = useQuery({
    queryKey: ['topic-companies', queryId, stateCode ?? null, stateCode ? city : null],
    queryFn: () => fetchTopicCompanies(queryId, stateCode, city),
    staleTime: 5 * 60 * 1000,
  })
  const companies = q.data?.companies ?? []
  const named = companies.filter((c) => c.meetings + c.decisions > 0)
  const unnamed = companies.filter((c) => c.meetings + c.decisions === 0)
  const search = (c: TopicCompany) =>
    `/search?q=${encodeURIComponent(companySearchTerm(c.company_name, c.newest?.evidence))}&sort=date_desc${stateCode ? `&state=${stateCode}` : ''}${stateCode && city ? `&city=${encodeURIComponent(city)}` : ''}`

  return (
    <section className="home-topic-companies" aria-labelledby="home-topic-companies-h">
      <h3 id="home-topic-companies-h" className="font-mono-x">
        Companies named · {title} · {scopeLabel}
      </h3>
      {q.isError ? (
        <p className="home-topic-companies-note">Companies could not be loaded right now.</p>
      ) : q.isPending ? (
        <p className="home-topic-companies-note">Loading companies…</p>
      ) : companies.length === 0 ? (
        <p className="home-topic-companies-note">No companies are tracked for this topic yet.</p>
      ) : (
        <>
          {named.length === 0 ? (
            <p className="home-topic-companies-note">None of the companies tracked for {title.toLowerCase()} is named in {scopeLabel === 'National' ? 'any meeting on record' : `${scopeLabel}'s meetings on record`}.</p>
          ) : (
            <ul className="home-topic-companies-list">
              {named.map((c) => {
                const brands = c.aliases.filter((a) => a !== c.company_name && !a.includes(','))
                return (
                  <li key={c.company_key} className="home-topic-company">
                    <p className="home-topic-company-name">
                      {c.master_org_id ? (
                        <Link to={`/organizations/${encodeURIComponent(c.master_org_id)}`}>{c.company_name}</Link>
                      ) : (
                        c.company_name
                      )}
                      {brands.length > 0 && <span className="home-topic-company-brands"> · {brands.slice(0, 3).join(', ')}</span>}
                    </p>
                    <p className="home-topic-company-counts">
                      <Link to={search(c)}>
                        {fmt(c.meetings)} {c.meetings === 1 ? 'meeting' : 'meetings'}
                      </Link>
                      {c.decisions > 0 && ` · ${fmt(c.decisions)} ${c.decisions === 1 ? 'decision' : 'decisions'}`}
                    </p>
                    {c.newest?.evidence && (
                      <blockquote className="home-topic-company-quote">
                        “{highlightSnippet(c.newest.evidence)}”
                        <footer>
                          {[c.newest.jurisdiction_name, c.newest.state_code].filter(Boolean).join(', ')}
                          {fmtDate(c.newest.date) ? ` · ${fmtDate(c.newest.date)}` : ''}
                          {c.newest.url &&
                            (c.newest.url.startsWith('/') ? (
                              <> · <Link to={c.newest.url}>Open</Link></>
                            ) : (
                              <> · <a href={c.newest.url} target="_blank" rel="noopener noreferrer">Watch ↗</a></>
                            ))}
                        </footer>
                      </blockquote>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
          {unnamed.length > 0 && named.length > 0 && (
            <p className="home-topic-companies-note">
              Not named {scopeLabel === 'National' ? 'in any meeting on record' : `in ${scopeLabel}'s meetings on record`}: {unnamed.map((c) => c.company_name).join(', ')}.
            </p>
          )}
        </>
      )}
    </section>
  )
}
