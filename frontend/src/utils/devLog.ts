/** Set `VITE_DEBUG_HOME=true` in `.env.local` to enable Home page trace logs. */
export function createDevLogger(envFlag: string): (...args: unknown[]) => void {
  const enabled =
    import.meta.env.DEV && import.meta.env[envFlag as keyof ImportMetaEnv] === 'true'
  return (...args: unknown[]) => {
    if (enabled) console.log(...args)
  }
}

export const homeLog = createDevLogger('VITE_DEBUG_HOME')
