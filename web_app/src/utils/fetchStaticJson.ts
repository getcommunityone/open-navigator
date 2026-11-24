/** Thrown when a static data file is not there to be read. */
export class StaticDataMissingError extends Error {
  constructor(
    public readonly url: string,
    reason: string,
  ) {
    super(`${url}: ${reason}`)
    this.name = 'StaticDataMissingError'
  }
}

/**
 * Fetch a JSON file from the static `/data` tree, and fail loudly when it is not there.
 *
 * A missing file does not always come back as a 404: the dev server and the single-page fallback
 * both answer with the app's own HTML page and status 200. Without this check the caller sees a
 * JSON parse error at best and a silently empty page at worst.
 */
export async function fetchStaticJson<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) throw new StaticDataMissingError(url, `HTTP ${r.status}`)
  const type = (r.headers.get('content-type') ?? '').toLowerCase()
  if (type.includes('text/html')) throw new StaticDataMissingError(url, 'the server answered with a web page, not the file')
  try {
    return (await r.json()) as T
  } catch {
    throw new StaticDataMissingError(url, 'the file is not valid JSON')
  }
}
