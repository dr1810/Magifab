import type { LucideIcon } from 'lucide-react'
import { CircleHelp, Clock3, Heart, Lightbulb, Package, Users } from 'lucide-react'

export type VisualAidKind = 'relationships' | 'timeline' | 'cause' | 'emotion' | 'object' | 'summary' | 'conversation' | 'memory' | 'location'

export type Prompt = {
  id: string
  label: string
  question: string
  answer: string
  kind: VisualAidKind
  icon: LucideIcon
  target: { x: number; y: number }
}

export const movie = {
  title: 'The Lumina Garden',
  year: '2026',
  duration: '1h 42m',
  genre: 'Family fantasy',
  currentTime: 3442,
  totalTime: 6120,
  subtitle: '“We can choose our own way home.”',
  scene: 'The glasshouse clearing',
  companion: { name: 'Lumi', personality: 'Patient guide', mode: 'Gentle nudges' },
} as const

export const prompts: Prompt[] = [
  { id: 'who', label: 'Who is this?', question: 'Meet Elara', answer: 'Elara is the garden keeper’s daughter. She found the glowing seed and wants to protect it.', kind: 'relationships', icon: Users, target: { x: 45, y: 48 } },
  { id: 'what', label: 'What is happening?', question: 'This moment', answer: 'Elara is showing Rowan the seed. They have decided to leave the garden together before the storm arrives.', kind: 'timeline', icon: Clock3, target: { x: 55, y: 52 } },
  { id: 'why', label: 'Why is this important?', question: 'Why it matters', answer: 'The seed is their clue to finding the garden’s hidden exit. Keeping it safe gives them a way home.', kind: 'cause', icon: Lightbulb, target: { x: 51, y: 42 } },
  { id: 'feeling', label: 'What are they feeling?', question: 'Their feelings', answer: 'Elara feels hopeful but nervous. Rowan is worried about the storm, yet trusts Elara’s plan.', kind: 'emotion', icon: Heart, target: { x: 54, y: 51 } },
  { id: 'object', label: 'What is that?', question: 'The glowing seed', answer: 'This seed lights up when it is close to the hidden path. It is an important guide, not just a pretty object.', kind: 'object', icon: Package, target: { x: 50, y: 38 } },
  { id: 'remember', label: 'What should I remember?', question: 'A quick reminder', answer: 'Earlier, Elara learned that the seed glows near the old moon gate. The moon gate is their way out.', kind: 'memory', icon: CircleHelp, target: { x: 48, y: 40 } },
]
