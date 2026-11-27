import { mergeConfig } from 'vite'
import base from './vite.config'
// Temporary (screenshots only): own port and API, never 5173/8001.
export default mergeConfig(base, {
  cacheDir: process.env.SHOT_CACHE,
  server: { port: Number(process.env.SHOT_PORT), strictPort: true, proxy: { '/api': { target: process.env.SHOT_API } } },
})
