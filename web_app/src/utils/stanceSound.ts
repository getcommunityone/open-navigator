// Synthesized sound cues for the Data Center Challenge (#899). No audio files: every cue is a few oscillator notes shaped by a
// gain envelope in the Web Audio API. The cues are our own short motifs and are neutral: none of them says right or wrong, and
// none counts points. Scheduling is pure (`cueNotes`); the audio wiring is thin and never throws, so a browser without Web
// Audio simply stays quiet.

export type Cue = 'open' | 'question' | 'lock' | 'bar' | 'finish'

export interface CueNote {
  /** Hertz. */
  freq: number
  /** Seconds after the cue starts. */
  start: number
  /** Seconds the note sounds, release included. */
  duration: number
  type: OscillatorType
  /** 0 to 1, relative to the other notes of the cue. */
  gain: number
}

/** The device setting: "on" or "off", default on. */
export const SOUND_KEY = 'stance.sound'
/** All cues go through one master gain this quiet. */
export const MASTER_GAIN = 0.15

const note = (freq: number, start: number, duration: number, type: OscillatorType = 'sine', gain = 1): CueNote => ({
  freq,
  start,
  duration,
  type,
  gain,
})

/** Notes of a cue. `step` raises the `bar` cue by a major third per scope (0 national, 1 state, 2 place). Pure. */
export function cueNotes(cue: Cue, step = 0): CueNote[] {
  switch (cue) {
    case 'open':
      // Two soft rising notes: a page turning.
      return [note(392, 0, 0.14), note(587.33, 0.09, 0.22, 'sine', 0.9)]
    case 'question':
      // A quick rising arpeggio that lands on a held top note: "your turn".
      return [note(523.25, 0, 0.12, 'triangle'), note(659.25, 0.08, 0.12, 'triangle'), note(783.99, 0.16, 0.22, 'triangle')]
    case 'lock':
      // A low, short, neutral click-thump: "noted". One pitch, no rise or fall.
      return [note(220, 0, 0.1, 'triangle'), note(220, 0.04, 0.14, 'sine', 0.6)]
    case 'bar': {
      const s = Math.min(Math.max(Math.round(step), 0), 4)
      const f = 523.25 * Math.pow(2, (s * 4) / 12)
      return [note(f, 0, 0.17), note(f * 2, 0, 0.09, 'sine', 0.35)]
    }
    case 'finish':
      // Three rising notes, then a held open fifth (no major or minor colour).
      return [
        note(392, 0, 0.18, 'triangle'),
        note(523.25, 0.12, 0.18, 'triangle'),
        note(587.33, 0.24, 0.18, 'triangle'),
        note(293.66, 0.4, 0.78, 'sine', 0.8),
        note(440, 0.4, 0.78, 'sine', 0.7),
      ]
  }
}

/** Seconds from the cue's start to the end of its last note. */
export const cueLength = (cue: Cue, step = 0): number => Math.max(...cueNotes(cue, step).map((n) => n.start + n.duration))

/** The saved setting, true when on or never set; storage that throws counts as the default. */
export function readSoundSetting(): boolean {
  try {
    return window.localStorage.getItem(SOUND_KEY) !== 'off'
  } catch {
    return true
  }
}

export function writeSoundSetting(on: boolean): void {
  try {
    window.localStorage.setItem(SOUND_KEY, on ? 'on' : 'off')
  } catch {
    /* storage can be blocked or full: the choice then lasts for this visit only */
  }
}

export interface SoundBoard {
  /** Play a cue; silent when sound is off, before the first click or key press, or without Web Audio. */
  play: (cue: Cue, step?: number) => void
  /** Turn sound on or off and remember the choice on this device. */
  setEnabled: (on: boolean) => void
  readonly enabled: boolean
  /** Start listening for the first gesture (done at creation unless `attach: false`; safe to call again). */
  attach: () => void
  /** Stop listening for the first gesture. */
  dispose: () => void
}

type AudioCtor = typeof AudioContext

function audioCtor(): AudioCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as { AudioContext?: AudioCtor; webkitAudioContext?: AudioCtor }
  return w.AudioContext ?? w.webkitAudioContext ?? null
}

/**
 * One board per page. The shared AudioContext is made only after the player's first pointer press or key press (and only when
 * sound is on), and resumed whenever it is suspended.
 */
export function createSoundBoard(opts: { attach?: boolean } = {}): SoundBoard {
  let enabled = readSoundSetting()
  let unlocked = false
  let ctx: AudioContext | null = null
  let master: GainNode | null = null
  let broken = false

  const ensure = (): AudioContext | null => {
    if (broken || !unlocked) return null
    try {
      if (!ctx) {
        const C = audioCtor()
        if (!C) {
          broken = true
          return null
        }
        ctx = new C()
        master = ctx.createGain()
        master.gain.value = MASTER_GAIN
        master.connect(ctx.destination)
      }
      if (ctx.state === 'suspended') void ctx.resume().catch(() => {})
      return ctx
    } catch {
      broken = true
      return null
    }
  }

  const onGesture = () => {
    unlocked = true
    if (enabled) ensure()
  }
  const events = ['pointerdown', 'keydown', 'touchstart'] as const
  let attached = false
  const attach = () => {
    if (attached || typeof window === 'undefined') return
    attached = true
    events.forEach((e) => window.addEventListener(e, onGesture, { capture: true, passive: true }))
  }
  if (opts.attach !== false) attach()

  return {
    play(cue, step = 0) {
      if (!enabled) return
      const c = ensure()
      if (!c || !master) return
      try {
        const t0 = c.currentTime + 0.02
        for (const n of cueNotes(cue, step)) {
          const osc = c.createOscillator()
          const env = c.createGain()
          osc.type = n.type
          osc.frequency.value = n.freq
          env.gain.setValueAtTime(0.0001, t0 + n.start)
          env.gain.linearRampToValueAtTime(0.9 * n.gain, t0 + n.start + 0.012)
          env.gain.exponentialRampToValueAtTime(0.0001, t0 + n.start + n.duration)
          osc.connect(env)
          env.connect(master)
          osc.start(t0 + n.start)
          osc.stop(t0 + n.start + n.duration + 0.03)
        }
      } catch {
        /* a cue that cannot play is not worth an error */
      }
    },
    setEnabled(on) {
      enabled = on
      writeSoundSetting(on)
    },
    get enabled() {
      return enabled
    },
    attach,
    dispose() {
      attached = false
      if (typeof window !== 'undefined') events.forEach((e) => window.removeEventListener(e, onGesture, { capture: true }))
    },
  }
}
