import { adjacentScreens, screenLabel, type ScreenSection } from '../../utils/matrixStory'
import type { MatrixCtx } from './types'

/**
 * The end of a screen: a Continue control that names what comes next in words ("Continue: what changed since 2019") and, from
 * the second screen on, a quieter Back control that names the one before. Both are real buttons; the destination is in their
 * visible (and so accessible) name. They page the same way the keyboard does (`ctx.goTo`): scroll, focus the heading, replace
 * the URL. The last screen has no Continue; the action block gives it the way out.
 */
export default function ScreenPager({ ctx, section }: { ctx: MatrixCtx; section: ScreenSection }) {
  const { prev, next } = adjacentScreens(section)
  if (!prev && !next) return null
  return (
    <div className="folio-pager">
      {next && (
        <button type="button" className="folio-pager-next" onClick={() => ctx.goTo(next.domId)}>
          <span>Continue: {screenLabel(next.section, ctx.labelInput)}</span>
          <span aria-hidden="true" className="folio-pager-arrow">
            ↓
          </span>
        </button>
      )}
      {prev && (
        <button type="button" className="folio-pager-back" onClick={() => ctx.goTo(prev.domId)}>
          <span aria-hidden="true">↑</span> Back: {screenLabel(prev.section, ctx.labelInput)}
        </button>
      )}
    </div>
  )
}
