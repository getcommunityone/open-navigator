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
 * Tell a real file in the static `/data` tree from the app page served in its place.
 *
 * A missing file does not always come back as a 404: the dev server and the single-page fallback
 * answer with the app's HTML page and status 200. The real file's content type, though, depends on
 * the server: Vite says `application/geo+json` for a `.geojson` file, while Python's static server
 * has no entry for that extension and says `application/octet-stream` (#1266). So the test is
 * "a 2xx that is not a web page", never "a content type that says json".
 */
export function isServedDataFile(status: number, contentType: string | null): boolean {
  return servedDataFileStatus(status, contentType) === 'file'
}

/**
 * For a loop that walks back through vintages: `file` to read, `missing` to try the next vintage
 * (404, or the app page in place of the file), `error` for any other failure, which the caller
 * should surface rather than read as "no data".
 */
export function servedDataFileStatus(status: number, contentType: string | null): 'file' | 'missing' | 'error' {
  const isPage = (contentType ?? '').toLowerCase().includes('text/html')
  if (status === 404) return 'missing'
  if (status < 200 || status >= 300) return 'error'
  return isPage ? 'missing' : 'file'
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
  if (!isServedDataFile(r.status, r.headers.get('content-type'))) throw new StaticDataMissingError(url, 'the server answered with a web page, not the file')
  try {
    return (await r.json()) as T
  } catch {
    throw new StaticDataMissingError(url, 'the file is not valid JSON')
  }
}
