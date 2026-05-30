import createClient from 'openapi-fetch'
import type { paths } from './api.types'

/**
 * Typed API client generated from the FastAPI OpenAPI contract.
 *
 * Path/params/response shapes come from `api.types.ts` (run `npm run gen:api`
 * to refresh; CI gates drift). Prefer this over the hand-typed default export
 * in `./api` for new call sites and incremental migrations.
 *
 * The generated path keys are absolute (`/api/...`), so `baseUrl` is empty to
 * keep requests origin-relative — matching the production `/api` convention in
 * `./api` and the Vite dev proxy.
 */
export const apiTyped = createClient<paths>({ baseUrl: '' })
