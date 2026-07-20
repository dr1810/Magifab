import { Bot, Cat, Dog, Feather, PawPrint, PersonStanding, Sparkles, WandSparkles } from 'lucide-react'

type CompanionAvatarProps = {
  appearance?: string
  name: string
  size?: 'small' | 'medium'
}

function avatarFor(appearance = '') {
  if (/robot|orb|alien/i.test(appearance)) return { Icon: Bot, tone: 'robot' }
  if (/human/i.test(appearance)) return { Icon: PersonStanding, tone: 'human' }
  if (/owl/i.test(appearance)) return { Icon: Feather, tone: 'owl' }
  if (/cat/i.test(appearance)) return { Icon: Cat, tone: 'cat' }
  if (/dog/i.test(appearance)) return { Icon: Dog, tone: 'dog' }
  if (/fox|bear/i.test(appearance)) return { Icon: PawPrint, tone: 'fox' }
  if (/spirit|fantasy/i.test(appearance)) return { Icon: WandSparkles, tone: 'spirit' }
  return { Icon: Sparkles, tone: 'spirit' }
}

export function CompanionAvatar({ appearance, name, size = 'medium' }: CompanionAvatarProps) {
  const { Icon, tone } = avatarFor(appearance)
  return <span className={`companion-avatar ${tone} ${size}`} aria-hidden="true"><Icon size={size === 'small' ? 18 : 24} strokeWidth={1.8} /><span className="sr-only">{name}</span></span>
}
