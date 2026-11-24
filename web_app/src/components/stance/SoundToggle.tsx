interface Props {
  on: boolean
  onToggle: () => void
}

/** The sound switch in the top bar of every challenge screen. The choice is the caller's to remember. */
export default function SoundToggle({ on, onToggle }: Props) {
  return (
    <button type="button" className="folio-btn stance-sound" aria-pressed={on} onClick={onToggle} data-testid="stance-sound">
      <span aria-hidden="true" className="stance-sound-icon">
        {on ? '♪' : '×'}
      </span>
      {on ? 'Sound on' : 'Sound off'}
    </button>
  )
}
