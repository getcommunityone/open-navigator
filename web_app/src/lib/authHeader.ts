// Attach the stored bearer token to admin/control-plane fetches.
//
// The batch-jobs and deployments clients use plain fetch() (their endpoints
// aren't in the generated OpenAPI client), so they bypass the Authorization
// logic in lib/api.ts. These endpoints are admin-gated on the backend
// (require_admin), so every call must carry the JWT. Use this helper to build
// the headers.
export function authHeaders(
  base: Record<string, string> = {},
): Record<string, string> {
  const token = localStorage.getItem('auth_token')
  return token ? { ...base, Authorization: `Bearer ${token}` } : { ...base }
}
