/** Shared “report an issue” categories — home quick nav + Explore */
export type CauseIconKey = 'roads' | 'schools' | 'safety' | 'family' | 'health' | 'other'

export type CauseDef = {
  id: string
  iconKey: CauseIconKey
  label: string
  desc: string
  tag: string
  hot?: boolean
  /** In-app path or absolute URL */
  to: string
}

export const CAUSES: CauseDef[] = [
  {
    id: 'roads',
    iconKey: 'roads',
    label: 'Roads & Infrastructure',
    desc: 'Potholes, broken lights, sidewalks, flooding',
    tag: 'Most reported',
    hot: true,
    to: '/search?q=roads+infrastructure+potholes',
  },
  {
    id: 'schools',
    iconKey: 'schools',
    label: 'Schools & Youth',
    desc: 'After-school programs, mentors, foster care gaps',
    tag: 'Education',
    to: '/search?q=schools+youth+after-school',
  },
  {
    id: 'safety',
    iconKey: 'safety',
    label: 'Neighborhood Safety',
    desc: 'Watch programs, lighting, abandoned properties',
    tag: 'Crime & Safety',
    to: '/advocacy-topics',
  },
  {
    id: 'family',
    iconKey: 'family',
    label: 'Family & Parenting',
    desc: 'Parenting skills, childcare, family services',
    tag: 'Services',
    to: '/services',
  },
  {
    id: 'health',
    iconKey: 'health',
    label: 'Health & Wellness',
    desc: 'Clinics, mental health, food access',
    tag: 'Health',
    to: '/search?q=health+clinics+mental+food+access',
  },
  {
    id: 'other',
    iconKey: 'other',
    label: 'Something Else',
    desc: "Describe your issue — we'll find where it belongs",
    tag: 'Free text',
    to: '/opportunities?type=feedback',
  },
]
