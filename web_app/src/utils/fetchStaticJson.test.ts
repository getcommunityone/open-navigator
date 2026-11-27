import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchStaticJson, isServedDataFile, servedDataFileStatus, StaticDataMissingError } from './fetchStaticJson'

const respond = (body: string, init: ResponseInit) => vi.stubGlobal('fetch', vi.fn(async () => new Response(body, init)))

afterEach(() => vi.unstubAllGlobals())

describe('fetchStaticJson', () => {
  it('returns the parsed file', async () => {
    respond('{"vintage":"2024"}', { status: 200, headers: { 'content-type': 'application/json' } })
    expect(await fetchStaticJson<{ vintage: string }>('/data/x.json')).toEqual({ vintage: '2024' })
  })

  it('treats the app page served in place of a missing file as missing', async () => {
    respond('<!doctype html><html></html>', { status: 200, headers: { 'content-type': 'text/html; charset=utf-8' } })
    await expect(fetchStaticJson('/data/x.json')).rejects.toBeInstanceOf(StaticDataMissingError)
  })

  it('treats a 404 as missing and names the file', async () => {
    respond('nope', { status: 404 })
    await expect(fetchStaticJson('/data/census-map/manifest.json')).rejects.toThrow('/data/census-map/manifest.json: HTTP 404')
  })

  it('treats a broken file as missing', async () => {
    respond('{"vintage":', { status: 200, headers: { 'content-type': 'application/json' } })
    await expect(fetchStaticJson('/data/x.json')).rejects.toBeInstanceOf(StaticDataMissingError)
  })
})

describe('isServedDataFile (#1266)', () => {
  it('accepts a real file whatever json-ish or generic type the server gives it', () => {
    expect(isServedDataFile(200, 'application/json')).toBe(true)
    expect(isServedDataFile(200, 'application/geo+json')).toBe(true)
    // Production (Python static server) has no .geojson mime entry.
    expect(isServedDataFile(200, 'application/octet-stream')).toBe(true)
    expect(isServedDataFile(200, null)).toBe(true)
  })

  it('rejects the app page served in place of a missing file', () => {
    expect(isServedDataFile(200, 'text/html; charset=utf-8')).toBe(false)
    expect(isServedDataFile(200, 'TEXT/HTML')).toBe(false)
  })

  it('rejects error statuses', () => {
    expect(isServedDataFile(404, 'application/json')).toBe(false)
    expect(isServedDataFile(500, 'application/octet-stream')).toBe(false)
  })

  it('lets fetchStaticJson read a file served as octet-stream', async () => {
    respond('{"type":"FeatureCollection","features":[]}', { status: 200, headers: { 'content-type': 'application/octet-stream' } })
    expect(await fetchStaticJson('/data/census-map/2022/place_01.geojson')).toEqual({ type: 'FeatureCollection', features: [] })
  })
})

describe('servedDataFileStatus (#1266)', () => {
  it('sorts responses for the vintage fallback', () => {
    expect(servedDataFileStatus(200, 'application/octet-stream')).toBe('file')
    expect(servedDataFileStatus(200, 'application/geo+json')).toBe('file')
    expect(servedDataFileStatus(200, 'text/html')).toBe('missing')
    expect(servedDataFileStatus(404, 'text/html')).toBe('missing')
    expect(servedDataFileStatus(500, 'application/json')).toBe('error')
    expect(servedDataFileStatus(403, 'text/html')).toBe('error')
  })
})
