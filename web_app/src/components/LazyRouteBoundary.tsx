import { Component, Suspense, type ReactNode } from 'react'
import { lazyRouteFailureMessage } from '../utils/lazyRouteMessage'
import { isStaleChunkError, isStaleReloadPending, reloadOnceForStaleDeploy } from '../utils/staleDeploy'

interface Props {
  /** The page's name as the reader knows it, e.g. "How states compare". */
  name: string
  children: ReactNode
}

interface State {
  error: unknown
  failed: boolean
  /** A stale-deploy reload was started for this error; the new page is on its way. */
  reloading: boolean
}

/**
 * Wraps a lazily loaded page (#856): a loading state while its code arrives, and, if it fails to
 * load or throws while rendering, a message in place of the page so the rest of the site keeps working.
 * A chunk a deploy removed (#936) first gets one automatic reload (staleDeploy.ts); while it is on
 * its way the boundary says so instead of showing an error. The message shows when no reload is
 * made: the same file failed again after one, the browser is offline, or in development.
 */
export default class LazyRouteBoundary extends Component<Props, State> {
  state: State = { error: null, failed: false, reloading: false }

  static getDerivedStateFromError(error: unknown): Partial<State> {
    return { error, failed: true }
  }

  componentDidCatch(error: unknown) {
    // The vite:preloadError listener (main.tsx) has usually started the reload already; this
    // covers an error that reaches the boundary some other way.
    if (!import.meta.env.DEV && isStaleChunkError(error) && reloadOnceForStaleDeploy(error)) {
      this.setState({ reloading: true })
    }
  }

  render() {
    const { name, children } = this.props
    if (this.state.failed && (this.state.reloading || (isStaleReloadPending() && isStaleChunkError(this.state.error)))) {
      return (
        <p role="status" className="p-4 text-sm text-slate-600">
          Loading the latest version of {name}…
        </p>
      )
    }
    if (this.state.failed) {
      const m = lazyRouteFailureMessage(name, this.state.error)
      return (
        <div role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-semibold">{m.title}</p>
          <p className="mt-1 break-words font-mono text-xs">{m.detail}</p>
          <p className="mt-2">{m.hint}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-3 rounded border border-amber-400 bg-white px-3 py-1.5 text-sm font-medium text-amber-900 hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
          >
            Reload
          </button>
        </div>
      )
    }
    return (
      <Suspense
        fallback={
          <p role="status" className="p-4 text-sm text-slate-600">
            Loading {name}…
          </p>
        }
      >
        {children}
      </Suspense>
    )
  }
}
