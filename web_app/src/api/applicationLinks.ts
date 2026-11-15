// API client for data center job-application links (issue #248, DC-1.3).
// Public: GET /api/data-centers/application-links. Admin: /api/admin/application-links.
// Types are generated from the FastAPI schema (`npm run gen:api`).
import type { components } from '../lib/api.types'
import api from '../lib/api'
import { withSpan } from '../instrumentation'

type Schemas = components['schemas']
export type ApplicationLink = Schemas['ApplicationLink']
export type ApplicationLinksResponse = Schemas['ApplicationLinksResponse']
export type AdminApplicationLink = Schemas['AdminApplicationLink']
export type AdminApplicationLinksResponse = Schemas['AdminApplicationLinksResponse']
export type ApplicationLinkIn = Schemas['ApplicationLinkIn']
export type ApplicationLinkPatch = Schemas['ApplicationLinkPatch']

const ADMIN = '/admin/application-links'

export async function fetchApplicationLinks(params: { state?: string; city?: string }): Promise<ApplicationLinksResponse> {
  const q: Record<string, string> = {}
  if (params.state) q.state = params.state
  if (params.city) q.city = params.city
  const scopeLevel = params.city ? 'city' : params.state ? 'state' : 'national'
  return withSpan(
    'data-centers.application-links.load',
    async (span) => {
      const res = await api.get<ApplicationLinksResponse>('/data-centers/application-links', { params: q })
      span.setAttribute('data_centers.application_links.count', res.data?.items?.length ?? 0)
      return res.data
    },
    { 'data_centers.scope_level': scopeLevel },
  )
}

export async function adminListApplicationLinks(staleOnly: boolean): Promise<AdminApplicationLinksResponse> {
  const res = await api.get<AdminApplicationLinksResponse>(ADMIN, { params: staleOnly ? { stale: 'true' } : {} })
  return res.data
}

export async function adminCreateApplicationLink(body: ApplicationLinkIn): Promise<AdminApplicationLink> {
  return (await api.post<AdminApplicationLink>(ADMIN, body)).data
}

export async function adminUpdateApplicationLink(id: number, body: ApplicationLinkPatch): Promise<AdminApplicationLink> {
  return (await api.patch<AdminApplicationLink>(`${ADMIN}/${id}`, body)).data
}

export async function adminDeleteApplicationLink(id: number): Promise<void> {
  await api.delete(`${ADMIN}/${id}`)
}

export async function adminCheckApplicationLink(id: number): Promise<AdminApplicationLink> {
  return withSpan('admin.application-links.check', async () => (await api.post<AdminApplicationLink>(`${ADMIN}/${id}/check`)).data)
}

export async function adminVerifyApplicationLink(id: number): Promise<AdminApplicationLink> {
  return (await api.post<AdminApplicationLink>(`${ADMIN}/${id}/verify`)).data
}
