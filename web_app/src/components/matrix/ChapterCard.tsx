import { chapterDomId, type Chapter } from '../../utils/matrixStory'
import TitleBlock from './TitleBlock'

/**
 * The full-width card that opens a chapter: a mono eyebrow ("Chapter 1 of 5 · Call to order"), the chapter title at display
 * size (it rises line by line, once, and a rule draws under it), and one sentence computed from the data in scope.
 */
export default function ChapterCard({ chapter, index, total, lead }: { chapter: Chapter; index: number; total: number; lead: string }) {
  const dom = chapterDomId(chapter.id)
  return (
    <section id={dom} className="folio-chapter" aria-labelledby={`${dom}-h`} data-chapter={chapter.id}>
      <TitleBlock as="h2" id={`${dom}-h`} eyebrow={`Chapter ${index + 1} of ${total} · ${chapter.meeting}`} text={chapter.title} variant="chapter" rule />
      <p className="folio-chapter-lead">{lead}</p>
    </section>
  )
}
