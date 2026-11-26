import { chapterDomId, type Chapter } from '../../utils/matrixStory'
import TitleBlock from './TitleBlock'

/**
 * The compact opener of a chapter. It sits above the chapter's first section and shares that screen with it: the chapter's
 * band phrase as a small mono line, then the chapter's finding as the title (a sentence computed from the data in scope, kept
 * to two lines by a clamp). The title rises line by line once and a rule draws under it.
 */
export default function ChapterCard({ chapter, title }: { chapter: Chapter; title: string }) {
  const dom = chapterDomId(chapter.id)
  return (
    <section id={dom} className="folio-chapter" aria-labelledby={`${dom}-h`} data-chapter={chapter.id}>
      <TitleBlock as="h2" id={`${dom}-h`} eyebrow={chapter.bandLabel} text={title} variant="chapter" rule />
    </section>
  )
}
