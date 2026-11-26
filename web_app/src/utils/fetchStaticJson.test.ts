import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchStaticJson, StaticDataMissingError } from './fetchStaticJson'

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
